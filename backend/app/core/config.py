"""
系统配置管理模块
使用 pydantic-settings 从环境变量加载配置
"""
from typing import Optional, List
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """系统配置类"""
    
    # ==================== 应用配置 ====================
    APP_NAME: str = "RAG Backend API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    
    # ==================== 数据库配置 ====================
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "rag_admin"
    DB_PASSWORD: str = "rag_jin"
    DB_NAME: str = "rag_system"
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 3600
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        # 对密码进行URL编码，处理特殊字符（如@、#等）
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"mysql+pymysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """构建异步数据库连接URL"""
        encoded_password = quote_plus(self.DB_PASSWORD)
        return f"mysql+aiomysql://{self.DB_USER}:{encoded_password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
    
    # ==================== Redis配置 ====================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    
    @property
    def REDIS_URL(self) -> str:
        """构建Redis连接URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # ==================== 会话管理配置 ====================
    # Redis会话配置
    SESSION_CONTEXT_TTL: int = 7200       # 上下文TTL: 2小时
    SESSION_ACTIVE_TTL: int = 86400       # 活跃会话列表TTL: 24小时
    
    # 上下文限制
    MAX_CONTEXT_TURNS: int = 10           # 最大对话轮次
    MAX_CONTEXT_TOKENS: int = 4000        # 最大上下文Token数
    
    # 会话清理配置
    SESSION_ARCHIVE_DAYS: int = 7         # 多少天未活跃后归档
    SESSION_DELETE_DAYS: int = 30         # 归档后多少天删除详情
    
    # ==================== Elasticsearch配置 ====================
    ES_HOST: str = "http://localhost:9200"
    ES_INDEX_NAME: str = "rag_document_chunks"
    
    # ==================== Milvus配置 ====================
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    # ==================== 安全配置 ====================
    # JWT配置
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    
    # API Key加密密钥（必须32字节）
    AES_ENCRYPTION_KEY: str = Field(..., min_length=32, max_length=32)
    
    # ==================== 文件存储配置 ====================
    FILE_STORAGE_PATH: str = "./data/files"
    MAX_FILE_SIZE: int = 52428800  # 50MB
    
    # ==================== Embedding模型配置 ====================
    EMBEDDING_MODEL_PATH: str = "./models/Qwen/Qwen3-Embedding-0___6B"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DEVICE: str = "auto"  # cpu/cuda/auto
    
    # ==================== 文本切分配置 ====================
    DEFAULT_CHUNK_SIZE: int = 500
    DEFAULT_CHUNK_OVERLAP: int = 50
    
    # ==================== CORS配置 ====================
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    CORS_ALLOW_CREDENTIALS: bool = True
    
    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """解析CORS origins为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # ==================== Celery配置 ====================
    USE_CELERY: bool = False  # 是否使用Celery异步处理，设为False则使用同步处理
    CELERY_TASK_QUEUE: str = "rag_tasks"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ==================== Kafka配置 ====================
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9094"  # 外部访问端口，内部服务应使用 kafka:9092
    KAFKA_CONSUMER_GROUP: str = "rag_group"
    
    # ==================== 初始化配置 ====================
    INIT_DB_ON_STARTUP: bool = True
    CREATE_DEFAULT_ADMIN: bool = True
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "Admin@123"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
