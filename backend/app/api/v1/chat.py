"""
对话问答API路由 (异步)
"""
import time
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.core.utils import get_proxy_config
from app.models.user import User
from app.services.context_manager import context_manager
from app.utils.redis_client import redis_client
from app.utils.es_client import es_client
from app.models.llm import LLM
from app.core.llm.factory import LLMFactory
from app.core.llm.base import LLMRequest, LLMMessage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ask", response_model=ChatResponse, summary="对话问答")
async def chat(
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    与机器人对话
    """
    # 1. 获取或创建会话
    session, is_new = await session_service.get_or_create_session(
        db=db,
        user=current_user,
        robot_id=chat_request.robot_id,
        session_id=chat_request.session_id
    )
    
    # 2. 获取机器人配置
    robot = await robot_service.get_robot_by_id(db, chat_request.robot_id, current_user)
    
    # 3. 获取关联的知识库
    knowledge_ids = await robot_service.get_robot_knowledge_ids(db, chat_request.robot_id)
    
    if not knowledge_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="机器人未关联任何知识库"
        )
    
    start_time = time.time()
    
    # 4. 执行带上下文的对话
    response = await rag_service.chat_with_context(
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
    await session_service.save_chat_message(
        db=db,
        session_id=session.session_id,
        role="user",
        content=chat_request.question
    )
    
    # 保存助手消息
    await session_service.save_chat_message(
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
async def chat_stream(
    chat_request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    与机器人对话（流式输出）
    """
    # 1. 获取或创建会话
    session, is_new = await session_service.get_or_create_session(
        db=db,
        user=current_user,
        robot_id=chat_request.robot_id,
        session_id=chat_request.session_id
    )

    # 2. 获取机器人配置
    robot = await robot_service.get_robot_by_id(db, chat_request.robot_id, current_user)

    # 3. 获取关联的知识库
    knowledge_ids = await robot_service.get_robot_knowledge_ids(db, chat_request.robot_id)

    if not knowledge_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="机器人未关联任何知识库"
        )

    # 4. 执行混合检索
    retrieval_start = time.time()
    contexts = await rag_service.hybrid_retrieve(
        db=db,
        robot=robot,
        knowledge_ids=knowledge_ids,
        query=chat_request.question,
        top_k=robot.top_k
    )
    retrieval_time = time.time() - retrieval_start

    # 5. 获取历史消息 (Async redis call)
    history_messages = await redis_client.get_context_messages(session.session_id)
    llm_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in history_messages
    ]

    # 6. 保存用户消息到数据库
    await session_service.save_chat_message(
        db=db,
        session_id=session.session_id,
        role="user",
        content=chat_request.question
    )

    from app.models.apikey import APIKey
    from app.core.security import api_key_crypto
    from sqlalchemy import select
    import json as json_util

    # 7. 获取LLM配置用于流式调用
    result = await db.execute(select(LLM).where(LLM.id == robot.chat_llm_id, LLM.status == 1))
    llm = result.scalar_one_or_none()
    if not llm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM模型不存在或已禁用"
        )

    result = await db.execute(select(APIKey).where(APIKey.llm_id == robot.chat_llm_id, APIKey.status == 1))
    apikey = result.scalar_one_or_none()
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

    messages = [LLMMessage(role="system", content=robot.system_prompt or "你是一个智能助手，请基于提供的知识库内容回答用户问题。")]
    if llm_history:
        messages.extend([LLMMessage(role=m["role"], content=m["content"]) for m in llm_history])

    user_content = f"""## 知识库上下文：
{context_text}

## 用户问题：
{chat_request.question}

请基于以上知识库内容回答用户问题。如果知识库中没有相关信息，请说明这一点。"""
    messages.append(LLMMessage(role="user", content=user_content))

    # 9. 获取厂商适配器并调用流式接口
    provider = LLMFactory.get_provider(
        provider_name=llm.provider,
        api_key=api_key,
        base_url=llm.base_url,
        api_version=llm.api_version
    )

    request = LLMRequest(
        messages=messages,
        model=llm.model_name,
        temperature=getattr(robot, 'temperature', 0.7),
        max_tokens=getattr(robot, 'max_tokens', 2000),
        stream=True
    )

    # 状态变量
    state = {
        "full_answer": "",
        "full_reasoning_content": "",
        "has_reasoning_started": False,
        "has_text_started": False,
        "usage": {}
    }

    current_session_id = session.session_id
    contexts_data = [ctx.model_dump() for ctx in contexts]

    async def generate_stream():
        def format_sse_event(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json_util.dumps(data)}\n\n"

        if contexts_data:
            yield format_sse_event("speech_type", {"type": "searchGuid", "title": f"引用 {len(contexts_data)} 篇资料作为参考"})
            for idx, ctx in enumerate(contexts_data):
                yield format_sse_event("speech_type", {
                    "type": "context",
                    "index": idx + 1,
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
            async for chunk in provider.chat_stream(request):
                # 处理思考内容
                if chunk.reasoning_delta:
                    state["full_reasoning_content"] += chunk.reasoning_delta
                    state["has_reasoning_started"] = True
                    if not state["has_text_started"]:
                        yield format_sse_event("speech_type", {"type": "reasoner"})
                        state["has_text_started"] = True
                    yield format_sse_event("speech_type", {
                        "type": "think",
                        "title": "思考中...",
                        "iconType": 9,
                        "content": chunk.reasoning_delta,
                        "status": 1
                    })

                # 处理回答内容
                if chunk.content_delta:
                    state["full_answer"] += chunk.content_delta
                    if state["full_reasoning_content"] and not state["has_text_started"]:
                        yield format_sse_event("speech_type", {"type": "reasoner"})
                        state["has_text_started"] = True
                    elif not state["has_text_started"] and not state["full_reasoning_content"]:
                        yield format_sse_event("speech_type", {"type": "text"})
                        state["has_text_started"] = True
                    yield format_sse_event("speech_type", {
                        "type": "text",
                        "msg": chunk.content_delta
                    })

                # 记录 usage
                if chunk.usage:
                    state["usage"] = chunk.usage

                # 处理结束
                if chunk.finish_reason:
                    if state["full_reasoning_content"]:
                        think_time = int(time.time() - retrieval_start)
                        yield format_sse_event("speech_type", {
                            "type": "think",
                            "title": f"已深度思考(用时{think_time}秒)",
                            "iconType": 7,
                            "content": "",
                            "status": 2
                        })

                    yield format_sse_event("speech_type", {
                        "type": "finished",
                        "session_id": current_session_id,
                        "token_usage": state["usage"],
                        "full_answer": state["full_answer"],
                        "full_reasoning_content": state["full_reasoning_content"]
                    })
        except Exception as e:
            logger.error(f"适配器调用失败: {e}")
            yield format_sse_event("speech_type", {
                "type": "text",
                "msg": f"错误: {str(e)}"
            })

    async def finally_save():
        """流结束后保存助手消息"""
        try:
            await session_service.save_chat_message(
                db=db,
                session_id=current_session_id,
                role="assistant",
                content=state["full_answer"],
                contexts=contexts_data,
                token_usage=state.get("usage", {}),
                time_metrics={"retrieval_time": retrieval_time}
            )

            # 更新Redis上下文 (Async)
            await context_manager.add_assistant_message(
                session_id=current_session_id,
                content=state["full_answer"],
                tokens=0
            )

            await redis_client.update_active_session(current_user.id, current_session_id)
        except Exception as e:
            logger.error(f"保存流式对话历史失败: {e}")

    async def generate_stream_with_save():
        """生成器：流式返回数据并在结束后保存"""
        try:
            async for chunk in generate_stream():
                yield chunk
        finally:
            await finally_save()

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
async def test_knowledge(
    test_request: KnowledgeTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    测试知识库检索功能
    """
    from app.services.knowledge_service import knowledge_service
    
    # 验证知识库权限
    knowledge = await knowledge_service.get_knowledge_by_id(db, test_request.knowledge_id, current_user)
    
    start_time = time.time()
    
    # 创建临时机器人对象
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
        raw_results = await rag_service._vector_retrieve_async(
            db=db,
            knowledge_ids=[test_request.knowledge_id],
            query=test_request.query,
            top_k=test_request.top_k
        )
        contexts = await _convert_to_retrieved_contexts_async(raw_results)
    elif test_request.retrieval_mode == "keyword":
        raw_results = await rag_service._keyword_retrieve_async(
            knowledge_ids=[test_request.knowledge_id],
            query=test_request.query,
            top_k=test_request.top_k
        )
        contexts = await _convert_to_retrieved_contexts_async(raw_results)
    else:  # hybrid
        contexts = await rag_service.hybrid_retrieve(
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


async def _convert_to_retrieved_contexts_async(raw_results: list) -> list:
    """
    将原始检索结果转换为RetrievedContext对象 (异步)
    """
    from app.schemas.chat import RetrievedContext
    
    contexts = []
    
    for result in raw_results:
        try:
            chunk_data = await es_client.get_chunk_by_id(result["chunk_id"])
            if chunk_data:
                contexts.append(RetrievedContext(
                    chunk_id=result["chunk_id"],
                    document_id=result["document_id"],
                    filename=chunk_data.get("filename", "unknown"),
                    content=chunk_data.get("content", ""),
                    score=min(result.get("score", 0.0), 1.0),
                    source=result.get("source", "unknown")
                ))
        except Exception as e:
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
async def get_conversation_history(
    session_id: str,
    message_limit: int = Query(default=50, ge=1, le=200, description="消息数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定会话的历史记录
    """
    return await session_service.get_session_detail(
        db=db,
        session_id=session_id,
        user=current_user,
        message_limit=message_limit
    )


@router.post("/sessions", response_model=SessionInfo, summary="创建新会话")
async def create_session(
    session_create: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建新的对话会话
    """
    session = await session_service.create_session(
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
async def list_sessions(
    robot_id: Optional[int] = Query(default=None, description="机器人ID筛选"),
    status_filter: str = Query(default="active", description="状态筛选: active/archived"),
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户的会话列表
    """
    return await session_service.get_user_sessions(
        db=db,
        user=current_user,
        robot_id=robot_id,
        status_filter=status_filter,
        skip=skip,
        limit=limit
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse, summary="获取会话详情")
async def get_session(
    session_id: str,
    message_limit: int = Query(default=50, ge=1, le=200, description="消息数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取会话详情（包含历史消息）
    """
    return await session_service.get_session_detail(
        db=db,
        session_id=session_id,
        user=current_user,
        message_limit=message_limit
    )


@router.put("/sessions/{session_id}", response_model=SessionInfo, summary="更新会话")
async def update_session(
    session_id: str,
    update_data: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新会话信息
    """
    session = await session_service.update_session(
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
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除会话（软删除）
    """
    await session_service.delete_session(
        db=db,
        session_id=session_id,
        user=current_user
    )
    return {"message": "会话已删除"}


@router.post("/feedback", summary="提交消息反馈")
async def submit_feedback(
    feedback_request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交对消息的反馈
    """
    await session_service.update_feedback(
        db=db,
        user=current_user,
        feedback_request=feedback_request
    )
    return {"message": "反馈已提交"}
