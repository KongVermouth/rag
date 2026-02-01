"""
RAG服务 - 检索增强生成 (异步)
"""
import os
import logging
import time
import uuid
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.robot import Robot
from app.models.knowledge import Knowledge
from app.models.llm import LLM
from app.models.apikey import APIKey
from app.schemas.chat import ChatRequest, ChatResponse, RetrievedContext
from app.utils.es_client import es_client
from app.utils.milvus_client import milvus_client
from app.utils.embedding import get_embedding_model
from app.utils.reranker import reranker
from app.services.context_manager import context_manager
from app.utils.redis_client import redis_client
from app.core.llm.factory import LLMFactory
from app.core.llm.base import LLMRequest, LLMMessage

logger = logging.getLogger(__name__)


class RAGService:
    """RAG服务类 - 负责检索增强生成"""

    def __init__(self):
        self.es_client = es_client
        self.milvus_client = milvus_client

    async def hybrid_retrieve(
        self,
        db: AsyncSession,
        robot: Robot,
        knowledge_ids: List[int],
        query: str,
        top_k: int = 5
    ) -> List[RetrievedContext]:
        """
        混合检索核心逻辑：
        1. 根据是否启用重排序(Rerank)确定初始召回数量 recall_k。
        2. 并行执行向量检索(Vector Search)和关键词检索(BM25)。
        3. 使用倒数排名融合算法(RRF)对两路检索结果进行初步融合。
        4. 如果启用了重排序，则对融合后的结果调用精排模型进行二次排序。
        5. 返回最终最相关的 top_k 个片段。
        """
        # 初始召回范围：如果启用了重排序，召回数量扩大 (例如 4 倍) 以保证精排的效果
        recall_k = top_k * 4 if robot.enable_rerank else top_k

        # 1. 向量检索 (语义相似度)
        vector_results = await self._vector_retrieve_async(
            db, knowledge_ids, query, recall_k
        )

        # 2. 关键词检索 (BM25 匹配)
        keyword_results = await self._keyword_retrieve_async(
            knowledge_ids, query, recall_k
        )

        # 3. 混合融合 (RRF 算法)
        merged_results = await self._merge_results_async(vector_results, keyword_results, recall_k)

        # 4. 重排序 (精排逻辑)
        if robot.enable_rerank and merged_results:
            docs = [ctx.content for ctx in merged_results]
            
            # 检查是否有配置远程重排序模型
            rerank_llm = None
            if robot.rerank_llm_id:
                l_stmt = select(LLM).where(LLM.id == robot.rerank_llm_id)
                l_result = await db.execute(l_stmt)
                rerank_llm = l_result.scalar_one_or_none()
            
            if rerank_llm and rerank_llm.base_url:
                # 使用远程重排序 API
                logger.info(f"使用远程重排序模型: {rerank_llm.model_name}")
                # 获取 API Key
                ak_stmt = select(APIKey).where(APIKey.llm_id == rerank_llm.id, APIKey.status == 1)
                ak_result = await db.execute(ak_stmt)
                apikey = ak_result.scalar_one_or_none()
                api_key = api_key_crypto.decrypt(apikey.api_key_encrypted) if apikey else ""
                
                provider = LLMFactory.get_provider(
                    provider_name=rerank_llm.provider,
                    api_key=api_key,
                    base_url=rerank_llm.base_url,
                    api_version=rerank_llm.api_version
                )
                
                rerank_results = await provider.rerank(
                    query=query,
                    texts=docs,
                    model=rerank_llm.model_name,
                    top_n=top_k
                )
                
                final_results = []
                for i, res in enumerate(rerank_results):
                    if isinstance(res, dict):
                        idx = res.get("index", i)
                        score = res.get("relevance_score", res.get("score", 0))
                    else:
                        idx = i
                        score = 0
                        
                    if idx < len(merged_results):
                        ctx = merged_results[idx]
                        ctx.score = float(score)
                        ctx.source = f"{ctx.source}+remote_rerank"
                        final_results.append(ctx)
                return final_results
            else:
                # 使用本地重排序模型 (BGE-Reranker 等)
                logger.info("使用本地重排序模型")
                loop = asyncio.get_running_loop()
                # rerank 是同步耗时操作，需在线程池执行
                sorted_indices_scores = await loop.run_in_executor(
                    None,
                    reranker.rerank,
                    query, docs, top_k
                )
                
                final_results = []
                for idx, score in sorted_indices_scores:
                    if idx < len(merged_results):
                        ctx = merged_results[idx]
                        ctx.score = float(score)  # 使用精排分数更新
                        ctx.source = f"{ctx.source}+local_rerank"
                        final_results.append(ctx)
                return final_results

        return merged_results[:top_k]

    async def _vector_retrieve_async(
        self,
        db: AsyncSession,
        knowledge_ids: List[int],
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """异步向量检索 (支持多知识库和不同Embedding模型)"""
        try:
            # 1. 获取所有知识库配置
            k_stmt = select(Knowledge).where(Knowledge.id.in_(knowledge_ids))
            k_result = await db.execute(k_stmt)
            knowledges = k_result.scalars().all()
            
            if not knowledges:
                return []

            # 2. 按 Embedding 模型分组知识库
            # {embed_llm_id: [knowledge1, knowledge2, ...]}
            model_groups = {}
            for kb in knowledges:
                mid = kb.embed_llm_id or 0  # 0 表示本地模型
                if mid not in model_groups:
                    model_groups[mid] = []
                model_groups[mid].append(kb)

            # 3. 对每个模型分组执行检索
            all_results = []
            
            for mid, group_kbs in model_groups.items():
                # 3.1 生成该模型的查询向量
                query_vector = None
                if mid == 0:
                    # 本地模型
                    logger.info("使用本地Embedding模型进行检索")
                    embedding_model = get_embedding_model()
                    # encode returns (1, dim) ndarray
                    query_vector = embedding_model.encode(query)[0].tolist()
                else:
                    # 获取远程模型配置
                    llm_stmt = select(LLM).where(LLM.id == mid)
                    llm_result = await db.execute(llm_stmt)
                    llm = llm_result.scalar_one_or_none()
                    
                    if llm and llm.base_url:
                        logger.info(f"使用远程Embedding模型: {llm.model_name} (ID: {mid})")
                        # 获取 API Key
                        ak_stmt = select(APIKey).where(APIKey.llm_id == llm.id, APIKey.status == 1)
                        ak_result = await db.execute(ak_stmt)
                        apikey = ak_result.scalar_one_or_none()
                        api_key = api_key_crypto.decrypt(apikey.api_key_encrypted) if apikey else ""
                        
                        provider = LLMFactory.get_provider(
                            provider_name=llm.provider,
                            api_key=api_key,
                            base_url=llm.base_url,
                            api_version=llm.api_version
                        )
                        
                        embeddings = await provider.embed(
                            texts=[query],
                            model=llm.model_name
                        )
                        query_vector = embeddings[0]
                    else:
                        # 回退到本地模型
                        logger.warning(f"远程模型 {mid} 配置无效，回退到本地模型")
                        embedding_model = get_embedding_model()
                        query_vector = embedding_model.encode(query)[0].tolist()

                if query_vector is None:
                    continue

                # 3.2 并发搜索该分组下的所有 Milvus 集合
                search_tasks = []
                for kb in group_kbs:
                    search_tasks.append(
                        self.milvus_client.search_vectors(
                            collection_name=kb.vector_collection_name,
                            query_vector=query_vector,
                            top_k=top_k
                        )
                    )
                
                task_results = await asyncio.gather(*search_tasks, return_exceptions=True)
                
                for i, res in enumerate(task_results):
                    if isinstance(res, Exception):
                        logger.error(f"知识库 {group_kbs[i].id} 向量检索失败: {res}")
                        continue
                    
                    for item in res:
                        all_results.append({
                            "chunk_id": item["chunk_id"],
                            "document_id": item["document_id"],
                            "score": item["score"],
                            "source": "vector",
                            "knowledge_id": group_kbs[i].id
                        })
            
            # 4. 按分数全局排序并取 top_k
            all_results.sort(key=lambda x: x["score"], reverse=True)
            return all_results[:top_k]
            
        except Exception as e:
            logger.error(f"异步向量检索失败: {str(e)}")
            return []

    async def _keyword_retrieve_async(
        self,
        knowledge_ids: List[int],
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词检索 (Async)"""
        try:
            results = await self.es_client.search_chunks(
                query,
                knowledge_ids,
                top_k
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

    async def _merge_results_async(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[RetrievedContext]:
        """
        合并检索结果 (RRF - Reciprocal Rank Fusion)
        
        RRF 算法逻辑：
        对于每个召回的文档，其最终分数 = Σ (1 / (k + rank))
        其中 k 是一个常量 (通常取 60)，rank 是该文档在某路检索结果中的排名。
        这种方法不需要对不同维度的分数进行归一化，能有效平衡语义搜索和关键词搜索。
        """
        merged_scores = {}

        # 处理向量检索结果 (语义召回)
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
            merged_scores[chunk_id]["rrf_score"] += 1 / (60 + rank + 1)

        # 处理关键词检索结果 (BM25 召回)
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
                # 如果两路都召回了，标记为 hybrid
                merged_scores[chunk_id]["keyword_score"] = result["score"]
                merged_scores[chunk_id]["source"] = "hybrid"

            merged_scores[chunk_id]["rrf_score"] += 1 / (60 + rank + 1)

        # 按 RRF 最终得分从高到低排序
        sorted_items = sorted(
            merged_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:top_k]

        if not sorted_items:
            return []

        # 批量从 Elasticsearch 获取完整的文本内容 (Context)
        chunk_ids = [item["chunk_id"] for item in sorted_items]
        try:
            # 使用 mget 批量查询，比循环单个查询更高效
            chunks_data_list = await self.es_client.get_chunks_by_ids(chunk_ids)
            # 建立 ID 到数据的映射以保持排序顺序
            chunk_map = {c["chunk_id"]: c for c in chunks_data_list}
            
            contexts = []
            for item in sorted_items:
                cid = item["chunk_id"]
                if cid in chunk_map:
                    c_data = chunk_map[cid]
                    contexts.append(RetrievedContext(
                        chunk_id=cid,
                        document_id=item["document_id"],
                        filename=c_data.get("filename", "unknown"),
                        content=c_data.get("content", ""),
                        score=item["rrf_score"],
                        source=item["source"]
                    ))
            return contexts
        except Exception as e:
            logger.error(f"批量获取检索内容失败: {e}")
            return []

    async def _call_llm_api(
        self,
        db: AsyncSession,
        llm_id: int,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """调用LLM API生成回答 (使用统一抽象层)"""
        result = await db.execute(select(LLM).where(LLM.id == llm_id, LLM.status == 1))
        llm = result.scalar_one_or_none()
        if not llm:
            raise ValueError(f"LLM模型不存在或已禁用: {llm_id}")
        
        result = await db.execute(select(APIKey).where(APIKey.llm_id == llm_id, APIKey.status == 1))
        apikey = result.scalar_one_or_none()
        if not apikey:
            raise ValueError(f"LLM {llm.name} 没有可用的API Key")
        
        from app.core.security import api_key_crypto
        api_key = api_key_crypto.decrypt(apikey.api_key_encrypted)
        
        provider = LLMFactory.get_provider(
            provider_name=llm.provider,
            api_key=api_key,
            base_url=llm.base_url,
            api_version=llm.api_version
        )
        
        request = LLMRequest(
            messages=[LLMMessage(role=m["role"], content=m["content"]) for m in messages],
            model=llm.model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        response = await provider.chat(request)
        
        return {
            "answer": response.content,
            "token_usage": {
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens
            }
        }

    async def generate_answer(
        self,
        db: AsyncSession,
        robot: Robot,
        question: str,
        contexts: List[RetrievedContext],
        session_id: str = None,
        history_messages: List[Dict[str, str]] = None
    ) -> ChatResponse:
        """生成回答 (Async)"""
        start_time = time.time()
        
        context_text = "\n\n".join([
            f"[文档{i+1}] {ctx.filename}\n{ctx.content}"
            for i, ctx in enumerate(contexts)
        ]) if contexts else "未找到相关的知识库内容"

        messages = []
        messages.append({"role": "system", "content": robot.system_prompt or "You are a helpful assistant."})
        if history_messages:
            messages.extend(history_messages)
        
        user_content = f"""## 知识库上下文：
{context_text}

## 用户问题：
{question}

请基于以上知识库内容回答用户问题。"""
        messages.append({"role": "user", "content": user_content})

        try:
            llm_result = await self._call_llm_api(
                db=db,
                llm_id=robot.chat_llm_id,
                messages=messages,
                temperature=robot.temperature,
                max_tokens=robot.max_tokens
            )
            answer = llm_result["answer"]
            token_usage = llm_result["token_usage"]
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            answer = f"抱歉，生成回答时出错: {str(e)}"
            token_usage = {}

        response_time = time.time() - start_time
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

    async def chat_with_context(
        self,
        db: AsyncSession,
        robot: Robot,
        knowledge_ids: List[int],
        question: str,
        session_id: str = None,
        user_id: int = None
    ) -> ChatResponse:
        """带上下文的对话 (Async)"""
        # 1. 检索
        contexts = await self.hybrid_retrieve(
            db=db,
            robot=robot,
            knowledge_ids=knowledge_ids,
            query=question,
            top_k=robot.top_k
        )
        
        # 2. 获取历史消息
        history_messages = []
        if session_id:
            try:
                history_messages = await redis_client.get_context_messages(session_id)
            except Exception:
                history_messages = []

        # 3. 生成回答
        response = await self.generate_answer(
            db=db,
            robot=robot,
            question=question,
            contexts=contexts,
            session_id=session_id,
            history_messages=[{"role": m["role"], "content": m["content"]} for m in history_messages]
        )
        
        # 4. 更新Redis上下文 (Async)
        if session_id:
            await context_manager.add_user_message(session_id, question)
            await context_manager.add_assistant_message(session_id, response.answer)
            await redis_client.update_active_session(user_id, session_id)
            
        return response

rag_service = RAGService()
