"""
对话问答API路由
"""
import time
import json
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import (
    ChatRequest, ChatResponse, KnowledgeTestRequest, KnowledgeTestResponse,
    SessionCreate, SessionUpdate, SessionInfo, SessionListResponse,
    SessionDetailResponse, FeedbackRequest, RetrievedContext
)
from app.services.robot_service import robot_service
from app.services.rag_service import rag_service
from app.services.session_service import session_service
from app.core.deps import get_current_user
from app.models.user import User
from app.services.context_manager import context_manager
from app.utils.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ask", response_model=ChatResponse, summary="对话问答")
def chat(
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    与机器人对话
    
    - **robot_id**: 机器人ID
    - **question**: 用户问题
    - **session_id**: 会话ID（可选，不传则创建新会话）
    - **stream**: 是否流式返回（暂不支持）
    
    流程：
    1. 获取或创建会话
    2. 获取机器人配置和关联的知识库
    3. 混合检索（向量+关键词）
    4. 构建Prompt并调用LLM生成回答（支持多轮对话上下文）
    5. 保存对话历史
    6. 返回回答和引用来源
    """
    # 1. 获取或创建会话
    session, is_new = session_service.get_or_create_session(
        db=db,
        user=current_user,
        robot_id=chat_request.robot_id,
        session_id=chat_request.session_id
    )
    
    # 2. 获取机器人配置
    robot = robot_service.get_robot_by_id(db, chat_request.robot_id, current_user)
    
    # 3. 获取关联的知识库
    knowledge_ids = robot_service.get_robot_knowledge_ids(db, chat_request.robot_id)
    
    if not knowledge_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="机器人未关联任何知识库"
        )
    
    start_time = time.time()
    
    # 4. 执行带上下文的对话
    response = rag_service.chat_with_context(
        db=db,
        robot=robot,
        knowledge_ids=knowledge_ids,
        session_id=session.session_id,
        question=chat_request.question,
        user_id=current_user.id
    )
    
    total_time_ms = int((time.time() - start_time) * 1000)
    
    # 5. 保存对话历史到MySQL
    # 保存用户消息
    session_service.save_chat_message(
        db=db,
        session_id=session.session_id,
        role="user",
        content=chat_request.question
    )
    
    # 保存助手消息
    session_service.save_chat_message(
        db=db,
        session_id=session.session_id,
        role="assistant",
        content=response.answer,
        contexts=[ctx.model_dump() for ctx in response.contexts],
        token_usage=response.token_usage,
        time_metrics={
            "total_time_ms": total_time_ms
        }
    )
    
    return response


@router.post("/ask/stream", summary="流式对话问答")
def chat_stream(
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    与机器人对话（流式输出）

    - **robot_id**: 机器人ID
    - **question**: 用户问题
    - **session_id**: 会话ID（可选，不传则创建新会话）

    使用SSE (Server-Sent Events) 流式返回生成的内容，支持思考过程折叠。
    流式格式遵循 event/data 格式：
    - event: speech_type, data: text → 普通文本回复
    - event: speech_type, data: reasoner → 思考过程
    - event: speech_type, data: search_with_text → 搜索结果
    """
    # 1. 获取或创建会话
    session, is_new = session_service.get_or_create_session(
        db=db,
        user=current_user,
        robot_id=chat_request.robot_id,
        session_id=chat_request.session_id
    )

    # 2. 获取机器人配置
    robot = robot_service.get_robot_by_id(db, chat_request.robot_id, current_user)

    # 3. 获取关联的知识库
    knowledge_ids = robot_service.get_robot_knowledge_ids(db, chat_request.robot_id)

    if not knowledge_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="机器人未关联任何知识库"
        )

    # 4. 执行混合检索
    retrieval_start = time.time()
    contexts = rag_service.hybrid_retrieve(
        db=db,
        robot=robot,
        knowledge_ids=knowledge_ids,
        query=chat_request.question,
        top_k=robot.top_k
    )
    retrieval_time = time.time() - retrieval_start

    # 5. 获取历史消息
    from app.utils.redis_client import redis_client
    history_messages = redis_client.get_context_messages(session.session_id)
    llm_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_messages
    ]

    # 6. 保存用户消息到数据库
    session_service.save_chat_message(
        db=db,
        session_id=session.session_id,
        role="user",
        content=chat_request.question
    )

    # 7. 获取LLM配置用于流式调用
    from app.models.llm import LLM
    from app.models.apikey import APIKey
    from app.core.security import api_key_crypto

    llm = db.query(LLM).filter(LLM.id == robot.chat_llm_id, LLM.status == 1).first()
    if not llm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM模型不存在或已禁用"
        )

    apikey = db.query(APIKey).filter(
        APIKey.llm_id == robot.chat_llm_id,
        APIKey.status == 1
    ).first()
    if not apikey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"LLM {llm.name} 没有可用的API Key"
        )

    api_key = api_key_crypto.decrypt(apikey.api_key_encrypted)

    # 8. 构建消息
    context_text = "\n\n".join([
        f"[文档{i+1}] {ctx.filename}\n{ctx.content}"
        for i, ctx in enumerate(contexts)
    ]) if contexts else "未找到相关的知识库内容"

    messages = []
    system_prompt = robot.system_prompt or "你是一个智能助手，请基于提供的知识库内容回答用户问题。"
    messages.append({"role": "system", "content": system_prompt})
    if llm_history:
        messages.extend(llm_history)

    user_content = f"""## 知识库上下文：
{context_text}

## 用户问题：
{chat_request.question}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请说明这一点。"""
    messages.append({"role": "user", "content": user_content})

    # 9. 流式调用LLM
    import httpx
    import json as json_util

    base_url = llm.base_url or "https://api.openai.com/v1"
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": llm.model_name,
        "messages": messages,
        "temperature": getattr(robot, 'temperature', 0.7),
        "max_tokens": getattr(robot, 'max_tokens', 2000),
        "stream": True
    }

    full_answer = ""
    full_reasoning_content = ""
    has_reasoning_started = False
    has_text_started = False

    # 预先获取 session_id，避免流式响应时 session 已过期
    current_session_id = session.session_id
    # 序列化 contexts 避免在生成器中访问 ORM 对象
    contexts_data = [ctx.model_dump() for ctx in contexts]

    def generate_stream():
        nonlocal full_answer, full_reasoning_content, has_reasoning_started, has_text_started

        def format_sse_event(event: str, data: dict) -> str:
            """格式化SSE事件，添加 event: 和 data: 前缀"""
            return f"event: {event}\ndata: {json_util.dumps(data)}\n\n"

        # 先发送搜索结果引用
        if contexts_data:
            yield format_sse_event("speech_type", {"type": "searchGuid", "title": f"引用 {len(contexts_data)} 篇资料作为参考"})
            # 发送每个引用文档
            for ctx in contexts_data:
                yield format_sse_event("speech_type", {
                    "type": "context",
                    "index": contexts_data.index(ctx) + 1,
                    "docId": ctx.get("chunk_id", ""),
                    "title": ctx.get("filename", "unknown"),
                    "url": "",
                    "sourceType": "knowledge_base",
                    "quote": ctx.get("content", "")[:500],
                    "publish_time": "",
                    "icon_url": "",
                    "web_site_name": "知识库",
                    "ref_source_weight": int(ctx.get("score", 0) * 5),
                    "content": ctx.get("content", "")
                })

        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        yield format_sse_event("speech_type", {
                            "type": "text",
                            "msg": f"API请求失败({response.status_code})"
                        })
                        return

                    for line in response.iter_lines():
                        if line:
                            # 兼容 str 和 bytes 类型
                            line_decoded = line.decode('utf-8') if isinstance(line, bytes) else line
                            if line_decoded.startswith('data: '):
                                data_str = line_decoded[6:]
                                if data_str == '[DONE]':
                                    break
                                try:
                                    data = json_util.loads(data_str)
                                    chunk = data.get("choices", [{}])[0].get("delta", {})

                                    # 获取思考内容（reasoning_content）
                                    if "reasoning_content" in chunk:
                                        reasoning_delta = chunk.get("reasoning_content", "")
                                        if reasoning_delta:
                                            full_reasoning_content += reasoning_delta
                                            has_reasoning_started = True
                                            if not has_text_started:  # 如果还没有开始输出文本，发送 reasoner 事件
                                                yield format_sse_event("speech_type", {"type": "reasoner"})
                                                has_text_started = True
                                            yield format_sse_event("speech_type", {
                                                "type": "think",
                                                "title": "思考中...",
                                                "iconType": 9,
                                                "content": reasoning_delta,
                                                "status": 1
                                            })

                                    # 获取内容增量
                                    content_delta = chunk.get("content", "")
                                    if content_delta:
                                        full_answer += content_delta
                                        # 如果思考内容已经开始，需要先发送 reasoner 事件
                                        if full_reasoning_content and not has_text_started:
                                            yield format_sse_event("speech_type", {"type": "reasoner"})
                                            has_text_started = True
                                        elif not has_text_started and not full_reasoning_content:
                                            # 没有思考内容，直接发送文本
                                            yield format_sse_event("speech_type", {"type": "text"})
                                            has_text_started = True
                                        yield format_sse_event("speech_type", {
                                            "type": "text",
                                            "msg": content_delta
                                        })

                                    # 检查是否完成
                                    if chunk.get("finish_reason"):
                                        usage = data.get("usage", {})
                                        token_usage = {
                                            "prompt_tokens": usage.get("prompt_tokens", 0),
                                            "completion_tokens": usage.get("completion_tokens", 0),
                                            "total_tokens": usage.get("total_tokens", 0)
                                        }

                                        # 发送思考完成事件
                                        if full_reasoning_content:
                                            think_time = int(time.time() - retrieval_start)
                                            yield format_sse_event("speech_type", {
                                                "type": "think",
                                                "title": f"已深度思考(用时{think_time}秒)",
                                                "iconType": 7,
                                                "content": "",
                                                "status": 2
                                            })

                                        # 发送完成信号
                                        yield format_sse_event("speech_type", {
                                            "type": "finished",
                                            "session_id": current_session_id,
                                            "token_usage": token_usage,
                                            "full_answer": full_answer,
                                            "full_reasoning_content": full_reasoning_content
                                        })
                                except json_util.JSONDecodeError:
                                    continue
        except Exception as e:
            yield format_sse_event("speech_type", {
                "type": "text",
                "msg": f"错误: {str(e)}"
            })

    def finally_save():
        """流结束后保存助手消息"""
        try:
            response_time = time.time()
            session_service.save_chat_message(
                db=db,
                session_id=current_session_id,
                role="assistant",
                content=full_answer,
                contexts=contexts_data,
                token_usage={},
                time_metrics={"retrieval_time": retrieval_time}
            )

            # 只更新Redis上下文的助手消息，用户消息已在流开始时保存
            context_manager.add_assistant_message(
                session_id=current_session_id,
                content=full_answer,
                tokens=0
            )

            redis_client.update_active_session(current_user.id, current_session_id)
        except Exception as e:
            logger.error(f"保存流式对话历史失败: {e}")

    def generate_stream_with_save():
        """生成器：流式返回数据并在结束后保存"""
        try:
            # 使用生成器迭代，在结束后调用 finally_save
            yield from generate_stream()
        finally:
            # 流结束后保存消息
            finally_save()

    # 返回流式响应
    return StreamingResponse(
        generate_stream_with_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/test", response_model=KnowledgeTestResponse, summary="测试知识库检索")
def test_knowledge(
    test_request: KnowledgeTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    测试知识库检索功能
    
    不调用LLM，仅返回检索到的相关文档片段
    
    - **knowledge_id**: 知识库ID
    - **query**: 测试查询
    - **top_k**: 返回Top-K结果
    - **retrieval_mode**: 检索模式（vector/keyword/hybrid）
    """
    import time
    from app.services.knowledge_service import knowledge_service
    from app.schemas.chat import RetrievedContext
    from app.utils.es_client import ESClient
    
    # 验证知识库权限
    knowledge = knowledge_service.get_knowledge_by_id(db, test_request.knowledge_id, current_user)
    
    start_time = time.time()
    
    # 创建临时机器人对象（用于检索）
    from app.models.robot import Robot
    temp_robot = Robot(
        id=0,
        user_id=current_user.id,
        name="temp",
        chat_llm_id=1,
        system_prompt="",
        top_k=test_request.top_k,
        temperature=0.7,
        max_tokens=2000
    )
    
    # 执行检索
    if test_request.retrieval_mode == "vector":
        raw_results = rag_service._vector_retrieve(
            db=db,
            knowledge_ids=[test_request.knowledge_id],
            query=test_request.query,
            top_k=test_request.top_k
        )
        # 转换为RetrievedContext，需要从ES获取完整内容
        contexts = _convert_to_retrieved_contexts(raw_results)
    elif test_request.retrieval_mode == "keyword":
        raw_results = rag_service._keyword_retrieve(
            knowledge_ids=[test_request.knowledge_id],
            query=test_request.query,
            top_k=test_request.top_k
        )
        # 转换为RetrievedContext，需要从ES获取完整内容
        contexts = _convert_to_retrieved_contexts(raw_results)
    else:  # hybrid
        contexts = rag_service.hybrid_retrieve(
            db=db,
            robot=temp_robot,
            knowledge_ids=[test_request.knowledge_id],
            query=test_request.query,
            top_k=test_request.top_k
        )
    
    retrieval_time = time.time() - start_time
    
    return KnowledgeTestResponse(
        query=test_request.query,
        retrieval_mode=test_request.retrieval_mode,
        results=contexts,
        retrieval_time=retrieval_time
)


def _convert_to_retrieved_contexts(raw_results: list) -> list:
    """
    将原始检索结果转换为RetrievedContext对象
    从ES获取完整的chunk内容
    """
    from app.schemas.chat import RetrievedContext
    from app.utils.es_client import ESClient
    
    es_client = ESClient()
    contexts = []
    
    for result in raw_results:
        try:
            chunk_data = es_client.get_chunk_by_id(result["chunk_id"])
            if chunk_data:
                contexts.append(RetrievedContext(
                    chunk_id=result["chunk_id"],
                    document_id=result["document_id"],
                    filename=chunk_data.get("filename", "unknown"),
                    content=chunk_data.get("content", ""),
                    score=min(result.get("score", 0.0), 1.0),  # 确保score在0-1之间
                    source=result.get("source", "unknown")
                ))
        except Exception as e:
            # 如果获取ES内容失败，仍然返回基本信息
            contexts.append(RetrievedContext(
                chunk_id=result["chunk_id"],
                document_id=result["document_id"],
                filename="unknown",
                content="内容获取失败",
                score=min(result.get("score", 0.0), 1.0),
                source=result.get("source", "unknown")
            ))
    
    return contexts


@router.get("/history/{session_id}", response_model=SessionDetailResponse, summary="获取会话历史")
def get_conversation_history(
    session_id: str,
    message_limit: int = Query(default=50, ge=1, le=200, description="消息数量限制"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定会话的历史记录
    
    - **session_id**: 会话ID
    - **message_limit**: 返回的消息数量限制
    """
    return session_service.get_session_detail(
        db=db,
        session_id=session_id,
        user=current_user,
        message_limit=message_limit
    )


# ==================== 会话管理接口 ====================

@router.post("/sessions", response_model=SessionInfo, summary="创建新会话")
def create_session(
    session_create: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新的对话会话
    
    - **robot_id**: 机器人ID
    - **title**: 会话标题（可选）
    """
    session = session_service.create_session(
        db=db,
        user=current_user,
        robot_id=session_create.robot_id,
        title=session_create.title
    )
    
    return SessionInfo(
        session_id=session.session_id,
        robot_id=session.robot_id,
        title=session.title,
        summary=session.summary,
        message_count=session.message_count,
        status=session.status,
        is_pinned=bool(session.is_pinned),
        last_message_at=session.last_message_at,
        created_at=session.created_at
    )


@router.get("/sessions", response_model=SessionListResponse, summary="获取会话列表")
def list_sessions(
    robot_id: Optional[int] = Query(default=None, description="机器人ID筛选"),
    status_filter: str = Query(default="active", description="状态筛选: active/archived"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的会话列表
    
    - **robot_id**: 按机器人筛选（可选）
    - **status_filter**: 按状态筛选
    - **skip**: 分页跳过
    - **limit**: 分页大小
    """
    return session_service.get_user_sessions(
        db=db,
        user=current_user,
        robot_id=robot_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="获取会话详情")
def get_session(
    session_id: str,
    message_limit: int = Query(default=50, ge=1, le=200, description="消息数量限制"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取会话详情（包含历史消息）
    """
    return session_service.get_session_detail(
        db=db,
        session_id=session_id,
        user=current_user,
        message_limit=message_limit
    )


@router.put("/sessions/{session_id}", response_model=SessionInfo, summary="更新会话")
def update_session(
    session_id: str,
    update_data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新会话信息
    
    - **title**: 会话标题
    - **is_pinned**: 是否置顶
    - **status**: 状态 (active/archived)
    """
    session = session_service.update_session(
        db=db,
        session_id=session_id,
        user=current_user,
        update_data=update_data
    )
    
    return SessionInfo(
        session_id=session.session_id,
        robot_id=session.robot_id,
        title=session.title,
        summary=session.summary,
        message_count=session.message_count,
        status=session.status,
        is_pinned=bool(session.is_pinned),
        last_message_at=session.last_message_at,
        created_at=session.created_at
    )


@router.delete("/sessions/{session_id}", summary="删除会话")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除会话（软删除）
    """
    session_service.delete_session(
        db=db,
        session_id=session_id,
        user=current_user
    )
    return {"message": "会话已删除"}


@router.post("/feedback", summary="提交消息反馈")
def submit_feedback(
    feedback_request: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交对消息的反馈
    
    - **message_id**: 消息ID
    - **feedback**: 1=有用, -1=无用
    - **comment**: 反馈评论（可选）
    """
    session_service.update_feedback(
        db=db,
        user=current_user,
        feedback_request=feedback_request
    )
    return {"message": "反馈已提交"}
