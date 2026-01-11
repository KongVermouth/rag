"""
对话问答API路由
"""
import time
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import (
    ChatRequest, ChatResponse, KnowledgeTestRequest, KnowledgeTestResponse,
    SessionCreate, SessionUpdate, SessionInfo, SessionListResponse,
    SessionDetailResponse, FeedbackRequest
)
from app.services.robot_service import robot_service
from app.services.rag_service import rag_service
from app.services.session_service import session_service
from app.core.deps import get_current_user
from app.models.user import User

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
