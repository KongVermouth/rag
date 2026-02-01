"""
FastAPI主应用入口
"""
import time
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.logger import setup_logging
from app.api.v1 import api_router
from app.core.exceptions import ElasticsearchIKException

# 创建FastAPI应用实例
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="企业级RAG知识问答系统后端API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# 配置日志
setup_logging()

# ==================== 异常处理器 ====================

@app.exception_handler(ElasticsearchIKException)
async def es_ik_exception_handler(request: Request, exc: ElasticsearchIKException):
    """处理ES IK分词器异常"""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": 400,
            "msg": exc.message,
            "error_type": "illegal_argument_exception"
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """自定义HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": exc.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """自定义数据验证异常处理"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": 422,
            "msg": "请求参数验证失败",
            "detail": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理"""
    logger.error(f"Global Exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 500,
            "msg": "服务器内部错误"
        }
    )

# ==================== 中间件配置 ====================

# 配置CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # 记录请求信息
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        
        # 记录响应信息
        logger.info(
            f"Response: {response.status_code} - "
            f"Time: {process_time:.2f}ms"
        )
        return response
    except Exception as e:
        # 记录异常
        logger.error(f"Request failed: {str(e)}")
        raise e


@app.get("/")
async def root():
    """根路径"""
    logger.debug("访问根路径")
    return {
        "message": "Welcome to RAG Backend API",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    logger.debug("执行健康检查")
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/health/es")
async def es_health_check():
    """检查 Elasticsearch IK 分词器状态"""
    from app.utils.es_client import es_client
    is_ok = await es_client.check_ik_analyzer()
    if is_ok:
        return {"status": "healthy", "analyzer": "ik_max_word"}
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "msg": "IK analyzer is not available"}
        )


# 注册API路由
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 初始化数据库
    if settings.INIT_DB_ON_STARTUP:
        from app.db.session import init_db
        logger.info(f"DEBUG: Initializing DB with URL: {settings.ASYNC_DATABASE_URL}")
        await init_db()
    
    # 校验 Elasticsearch IK 插件
    from app.utils.es_client import es_client
    if not await es_client.check_ik_analyzer():
        logger.critical("Elasticsearch IK 分词器不可用，服务停止启动！请参考 README 安装插件。")
        import sys
        sys.exit(1)
    
    logger.info(f"[START] {settings.APP_NAME} v{settings.APP_VERSION} 启动成功")
    logger.info(f"[DOCS] API文档: http://localhost:8000/docs")
    logger.info(f"[HEALTH] 健康检查: http://localhost:8000/health")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    logger.info(f"[STOP] {settings.APP_NAME} 正在关闭...")
    
    # 关闭异步客户端
    from app.utils.redis_client import redis_client
    from app.utils.es_client import es_client
    from app.utils.milvus_client import milvus_client
    
    await redis_client.close()
    await es_client.close()
    await milvus_client.close()
    logger.info("[STOP] 异步客户端连接已关闭")


if __name__ == "__main__":
    import uvicorn
    # 注意：这里移除了 log_level 参数，因为我们在 setup_logging 中已经配置了拦截
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
