"""
API v1 routes.
"""
from fastapi import APIRouter
from app.api.v1 import auth, users, llms, apikeys, knowledge, documents, robots, chat, recall

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(llms.router, prefix="/llms", tags=["LLM模型"])
api_router.include_router(apikeys.router, prefix="/apikeys", tags=["API密钥"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
api_router.include_router(documents.router, prefix="/documents", tags=["文档管理"])
api_router.include_router(robots.router, prefix="/robots", tags=["机器人"])
api_router.include_router(chat.router, prefix="/chat", tags=["对话问答"])
api_router.include_router(recall.router, prefix="/recall", tags=["召回测试"])
