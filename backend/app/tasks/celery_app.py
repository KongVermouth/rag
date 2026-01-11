"""
Celery应用配置
"""
from celery import Celery
from app.core.config import settings

# 创建Celery应用实例
celery_app = Celery(
    "rag_backend",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks"]
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 任务超时时间：30分钟
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 任务路由配置（可选）
celery_app.conf.task_routes = {
    "app.tasks.document_tasks.*": {"queue": "document_processing"},
}
