"""
RAG服务 - 检索增强生成
"""
import logging
import time
import uuid
import httpx
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.robot import Robot
from app.models.knowledge import Knowledge
from app.models.llm import LLM
from app.models.apikey import APIKey
from app.schemas.chat import ChatRequest, ChatResponse, RetrievedContext
from app.utils.es_client import ESClient
from app.utils.milvus_client import MilvusClient
from app.utils.embedding import get_embedding_model
from app.services.context_manager import context_manager
from app.core.security import api_key_crypto

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务类 - 负责检索增强生成"""

    def __init__(self):
        self.es_client = ESClient()
        self.milvus_client = MilvusClient()

    def hybrid_retrieve(
        self,
        db: Session,
        robot: Robot,
        knowledge_ids: List[int],
        query: str,
        top_k: int = 5
    ) -> List[RetrievedContext]:
        """
        混合检索：向量检索 + 关键词检索
        
        Args:
            db: 数据库会话
            robot: 机器人对象
            knowledge_ids: 知识库ID列表
            query: 查询文本
            top_k: 返回Top-K结果
            
        Returns:
            List[RetrievedContext]: 检索到的上下文列表
        """
        # 1. 向量检索
        vector_results = self._vector_retrieve(db, knowledge_ids, query, top_k)

        # 2. 关键词检索
        keyword_results = self._keyword_retrieve(knowledge_ids, query, top_k)

        # 3. 混合融合（简单合并，根据分数排序）
        merged_results = self._merge_results(vector_results, keyword_results, top_k)

        return merged_results

    def _vector_retrieve(
        self,
        db: Session,
        knowledge_ids: List[int],
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """向量检索"""
        # 获取查询向量
        embedding_model = get_embedding_model()
        query_vector = embedding_model.encode(query)[0].tolist()

        all_results = []

        # 对每个知识库进行检索
        for kb_id in knowledge_ids:
            knowledge = db.query(Knowledge).filter(Knowledge.id == kb_id).first()
            if not knowledge:
                continue

            try:
                # 在Milvus中检索
                results = self.milvus_client.search_vectors(
                    collection_name=knowledge.vector_collection_name,
                    query_vector=query_vector,
                    top_k=top_k
                )

                for result in results:
                    all_results.append({
                        "chunk_id": result["chunk_id"],
                        "document_id": result["document_id"],
                        "score": result["score"],
                        "source": "vector",
                        "knowledge_id": kb_id
                    })
            except Exception as e:
                logger.error(f"向量检索失败 (KB: {kb_id}): {e}")
                continue

        # 按分数排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    def _keyword_retrieve(
        self,
        knowledge_ids: List[int],
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词检索（BM25）"""
        try:
            results = self.es_client.search_chunks(
                query=query,
                knowledge_ids=knowledge_ids,
                top_k=top_k
            )

            return [{
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "score": r["score"],
                "source": "keyword",
                "knowledge_id": r["knowledge_id"]
            } for r in results]
        except Exception as e:
            logger.error(f"关键词检索失败: {e}")
            return []

    def _merge_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[RetrievedContext]:
        """
        合并检索结果
        使用RRF（Reciprocal Rank Fusion）算法
        """
        # 使用chunk_id去重并计算融合分数
        merged_scores = {}

        # 向量检索结果
        for rank, result in enumerate(vector_results):
            chunk_id = result["chunk_id"]
            if chunk_id not in merged_scores:
                merged_scores[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": result["document_id"],
                    "knowledge_id": result["knowledge_id"],
                    "vector_score": result["score"],
                    "keyword_score": 0,
                    "rrf_score": 0,
                    "source": "vector"
                }
            # RRF公式: 1 / (k + rank)，k通常取60
            merged_scores[chunk_id]["rrf_score"] += 1 / (60 + rank + 1)

        # 关键词检索结果
        for rank, result in enumerate(keyword_results):
            chunk_id = result["chunk_id"]
            if chunk_id not in merged_scores:
                merged_scores[chunk_id] = {
                    "chunk_id": chunk_id,
                    "document_id": result["document_id"],
                    "knowledge_id": result["knowledge_id"],
                    "vector_score": 0,
                    "keyword_score": result["score"],
                    "rrf_score": 0,
                    "source": "keyword"
                }
            else:
                merged_scores[chunk_id]["keyword_score"] = result["score"]
                merged_scores[chunk_id]["source"] = "hybrid"

            merged_scores[chunk_id]["rrf_score"] += 1 / (60 + rank + 1)

        # 按RRF分数排序
        sorted_results = sorted(
            merged_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:top_k]

        # 获取文档内容（从ES获取）
        contexts = []
        for result in sorted_results:
            try:
                chunk_data = self.es_client.get_chunk_by_id(result["chunk_id"])
                if chunk_data:
                    contexts.append(RetrievedContext(
                        chunk_id=result["chunk_id"],
                        document_id=result["document_id"],
                        filename=chunk_data.get("filename", "unknown"),
                        content=chunk_data.get("content", ""),
                        score=result["rrf_score"],
                        source=result["source"]
                    ))
            except Exception as e:
                logger.error(f"获取chunk内容失败: {e}")
                continue

        return contexts

    def _call_llm_api(
        self,
        db: Session,
        llm_id: int,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        调用LLM API生成回答
        
        Args:
            db: 数据库会话
            llm_id: LLM模型ID
            messages: 消息列表
            temperature: 生成温度
            max_tokens: 最大Token数
            
        Returns:
            Dict: 包含 answer 和 token_usage
        """
        # 1. 获取LLM配置
        llm = db.query(LLM).filter(LLM.id == llm_id, LLM.status == 1).first()
        if not llm:
            raise ValueError(f"LLM模型不存在或已禁用: {llm_id}")
        
        # 2. 获取可用的API Key
        apikey = db.query(APIKey).filter(
            APIKey.llm_id == llm_id,
            APIKey.status == 1
        ).first()
        if not apikey:
            raise ValueError(f"LLM {llm.name} 没有可用的API Key")
        
        # 解密API Key
        api_key = api_key_crypto.decrypt(apikey.api_key_encrypted)
        
        # 3. 根据 provider 调用不同的API
        provider = llm.provider.lower()
        
        if provider in ["openai", "qwen", "deepseek", "siliconflow", "minimax", "moonshot", "zhipu", "baichuan", "yi", "doubao"]:
            return self._call_openai_compatible(
                base_url=llm.base_url or "https://api.openai.com/v1",
                api_key=api_key,
                model=llm.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == "azure":
            return self._call_azure_openai(
                base_url=llm.base_url,
                api_key=api_key,
                model=llm.model_name,
                api_version=llm.api_version or "2024-02-15-preview",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif provider == "anthropic":
            return self._call_anthropic(
                api_key=api_key,
                model=llm.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            raise ValueError(f"不支持的LLM提供商: {provider}")
    
    def _call_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """调用OpenAI兼容的API（带重试机制）"""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(url, json=payload, headers=headers)
                    
                    # 检查响应状态码
                    if response.status_code == 200:
                        data = response.json()
                        return {
                            "answer": data["choices"][0]["message"]["content"],
                            "token_usage": {
                                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                                "total_tokens": data.get("usage", {}).get("total_tokens", 0)
                            }
                        }
                    
                    # 429 错误 - 速率限制，需要重试
                    elif response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                        wait_time = min(retry_after, 30)  # 最多等待30秒
                        logger.warning(f"API速率限制(429)，{wait_time}秒后重试... (第{attempt + 1}次)")
                        
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue
                        else:
                            raise ValueError(
                                f"API请求频率超限，请稍后重试。"
                                f"如持续出现，请检查API Key配额或联系服务提供商。"
                            )
                    
                    # 401/403 错误 - 认证失败
                    elif response.status_code in [401, 403]:
                        raise ValueError(
                            f"API认证失败({response.status_code})，请检查API Key是否正确或已过期"
                        )
                    
                    # 400 错误 - 请求参数错误
                    elif response.status_code == 400:
                        error_detail = response.text[:200]
                        raise ValueError(f"API请求参数错误: {error_detail}")
                    
                    # 5xx 错误 - 服务器错误，可重试
                    elif response.status_code >= 500:
                        logger.warning(f"API服务器错误({response.status_code})，重试中... (第{attempt + 1}次)")
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)  # 指数退避
                            continue
                        else:
                            raise ValueError(f"API服务器错误({response.status_code})，请稍后重试")
                    
                    # 其他错误
                    else:
                        response.raise_for_status()
                        
            except httpx.TimeoutException:
                logger.warning(f"API请求超时，重试中... (第{attempt + 1}次)")
                last_error = "请求超时，请稍后重试"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except httpx.ConnectError:
                logger.warning(f"API连接失败，重试中... (第{attempt + 1}次)")
                last_error = "无法连接到API服务器，请检查网络或base_url配置"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except ValueError:
                # 重新抛出自定义的ValueError
                raise
            except Exception as e:
                last_error = str(e)
                logger.error(f"API调用异常: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        # 所有重试都失败
        raise ValueError(f"API调用失败: {last_error}")
    
    def _call_azure_openai(
        self,
        base_url: str,
        api_key: str,
        model: str,
        api_version: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """调用Azure OpenAI API"""
        url = f"{base_url.rstrip('/')}/openai/deployments/{model}/chat/completions?api-version={api_version}"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        return {
            "answer": data["choices"][0]["message"]["content"],
            "token_usage": {
                "prompt_tokens": data.get("usage", {}).get("prompt_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("completion_tokens", 0),
                "total_tokens": data.get("usage", {}).get("total_tokens", 0)
            }
        }
    
    def _call_anthropic(
        self,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """调用Anthropic Claude API"""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # 提取system prompt
        system_prompt = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                filtered_messages.append(msg)
        
        payload = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        return {
            "answer": data["content"][0]["text"],
            "token_usage": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
            }
        }

    def generate_answer(
        self,
        db: Session,
        robot: Robot,
        question: str,
        contexts: List[RetrievedContext],
        session_id: str = None,
        history_messages: List[Dict[str, str]] = None
    ) -> ChatResponse:
        """
        生成回答
        
        Args:
            db: 数据库会话
            robot: 机器人对象
            question: 用户问题
            contexts: 检索到的上下文
            session_id: 会话ID
            history_messages: 历史消息列表（可选，用于多轮对话）
            
        Returns:
            ChatResponse: 对话响应
        """
        start_time = time.time()

        # 构建检索上下文文本
        context_text = "\n\n".join([
            f"[文档{i+1}] {ctx.filename}\n{ctx.content}"
            for i, ctx in enumerate(contexts)
        ]) if contexts else "未找到相关的知识库内容"

        # 构建完整的消息列表（支持多轮对话）
        messages = []
        
        # 1. 系统提示词
        system_prompt = robot.system_prompt or "你是一个智能助手，请基于提供的知识库内容回答用户问题。"
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # 2. 历史对话（如果有）
        if history_messages:
            messages.extend(history_messages)
        
        # 3. 当前问题（包含检索上下文）
        user_content = f"""## 知识库上下文：
{context_text}

## 用户问题：
{question}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请说明这一点。"""
        messages.append({
            "role": "user",
            "content": user_content
        })

        # 调用LLM生成回答
        try:
            llm_result = self._call_llm_api(
                db=db,
                llm_id=robot.chat_llm_id,
                messages=messages,
                temperature=getattr(robot, 'temperature', 0.7),
                max_tokens=getattr(robot, 'max_tokens', 2000)
            )
            answer = llm_result["answer"]
            token_usage = llm_result["token_usage"]
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            answer = f"抱歉，生成回答时出错: {str(e)}"
            token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        response_time = time.time() - start_time

        # 使用传入的session_id或生成新的
        if not session_id:
            session_id = str(uuid.uuid4())

        return ChatResponse(
            session_id=session_id,
            question=question,
            answer=answer,
            contexts=contexts,
            token_usage=token_usage,
            response_time=response_time
        )
    
    def chat_with_context(
        self,
        db: Session,
        robot: Robot,
        knowledge_ids: List[int],
        session_id: str,
        question: str,
        user_id: int
    ) -> ChatResponse:
        """
        带上下文的对话（支持多轮对话）
        
        Args:
            db: 数据库会话
            robot: 机器人对象
            knowledge_ids: 知识库ID列表
            session_id: 会话ID
            question: 用户问题
            user_id: 用户ID
            
        Returns:
            ChatResponse: 对话响应
        """
        retrieval_start = time.time()
        
        # 1. 获取或初始化上下文
        context_manager.get_or_load_context(
            db=db,
            session_id=session_id,
            user_id=user_id,
            robot_id=robot.id,
            system_prompt=robot.system_prompt or ""
        )
        
        # 2. 基于上下文重写查询（可选，用于提升检索效果）
        # rewritten_query = context_manager.rewrite_query_with_context(session_id, question)
        rewritten_query = question  # 简化处理，直接使用原始查询
        
        # 3. 执行混合检索
        contexts = self.hybrid_retrieve(
            db=db,
            robot=robot,
            knowledge_ids=knowledge_ids,
            query=rewritten_query,
            top_k=robot.top_k
        )
        
        retrieval_time = time.time() - retrieval_start
        
        # 4. 获取历史消息用于构建Prompt
        from app.utils.redis_client import redis_client
        history_messages = redis_client.get_context_messages(session_id)
        
        # 转换为LLM消息格式
        llm_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history_messages
        ]
        
        generation_start = time.time()
        
        # 5. 生成回答
        response = self.generate_answer(
            db=db,
            robot=robot,
            question=question,
            contexts=contexts,
            session_id=session_id,
            history_messages=llm_history
        )
        
        generation_time = time.time() - generation_start
        
        # 6. 更新Redis上下文（添加当前轮对话）
        context_manager.add_user_message(
            session_id=session_id,
            content=question,
            tokens=response.token_usage.get("prompt_tokens", 0)
        )
        context_manager.add_assistant_message(
            session_id=session_id,
            content=response.answer,
            tokens=response.token_usage.get("completion_tokens", 0)
        )
        
        # 更新活跃会话时间
        redis_client.update_active_session(user_id, session_id)
        
        logger.info(
            f"对话完成: session={session_id}, "
            f"retrieval={retrieval_time:.2f}s, generation={generation_time:.2f}s"
        )
        
        return response


# 全局RAG服务实例
rag_service = RAGService()
