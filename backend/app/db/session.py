"""
数据库会话管理 (异步)
"""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select
from app.core.config import settings

logger = logging.getLogger(__name__)

# 创建异步数据库引擎
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # 连接前先ping，确保连接有效
    echo=settings.DEBUG,  # 开发模式下打印SQL语句
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 创建基类
Base = declarative_base()


async def init_db():
    """初始化数据库，创建所有表"""
    from app.db.base import Base as AppBase  # 确保所有模型已加载
    async with engine.begin() as conn:
        # 也可以在这里执行其他初始化逻辑
        # await conn.run_sync(AppBase.metadata.drop_all) # 危险：不要在生产环境使用
        await conn.run_sync(AppBase.metadata.create_all)
    
    # 插入初始化种子数据
    from app.models.user import User
    from app.models.llm import LLM
    from app.models.knowledge import Knowledge
    from app.core.security import get_password_hash
    
    async with AsyncSessionLocal() as session:
        # 1. 检查并创建默认管理员
        result = await session.execute(select(User).where(User.id == 1))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                id=1,
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("Admin@123"),
                role="admin",
                status=1
            )
            session.add(admin)
            logger.info("创建默认管理员用户 (ID: 1)")

        # 2. 检查并创建默认 Embedding 模型
        result = await session.execute(select(LLM).where(LLM.id == 1))
        llm = result.scalar_one_or_none()
        if not llm:
            llm = LLM(
                id=1,
                user_id=1,
                name="Default Embedding",
                provider="local",
                model_name="qwen-v1",
                model_type="embedding",
                status=1
            )
            session.add(llm)
            logger.info("创建默认 Embedding 模型 (ID: 1)")

        # 3. 检查并创建默认知识库 (ID: 1)
        result = await session.execute(select(Knowledge).where(Knowledge.id == 1))
        kb = result.scalar_one_or_none()
        if not kb:
            kb = Knowledge(
                id=1,
                user_id=1,
                name="示例知识库",
                description="系统自动生成的示例知识库",
                embed_llm_id=1,
                vector_collection_name="kb_1_default",
                status=1
            )
            session.add(kb)
            logger.info("创建初始知识库数据 (ID: 1)")
        
        await session.commit()

    logger.info("数据库初始化及种子数据检查完成")


async def get_db() -> AsyncSession:
    """
    获取数据库会话的依赖注入函数 (异步)
    用于FastAPI的Depends
    """
    async with AsyncSessionLocal() as session:
        try:
            # logger.debug("创建数据库会话")
            yield session
        except Exception as e:
            logger.error(f"数据库会话异常: {e}")
            raise
        finally:
            # logger.debug("关闭数据库会话")
            await session.close()
