"""
Worker 专用日志配置模块
为每个 Worker 任务提供独立的日志文件、分级记录、轮转策略及异常捕获
"""
import sys
from pathlib import Path
from loguru import logger
from typing import Dict, Any

# 日志根目录
LOG_DIR = Path("logs/workers")

# 移除默认的 loguru handler
logger.remove()

# 1. 统一的控制台输出 (显示所有 Worker 的日志)
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <magenta>{extra[worker]}</magenta> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    enqueue=True,
    backtrace=True,
    diagnose=True
)

# 用于记录已经初始化过的 worker logger
_initialized_workers = set()

def get_worker_logger(worker_name: str):
    """
    获取指定 Worker 的 Logger 实例。
    如果该 Worker 尚未在当前进程中初始化，则为其添加文件输出。
    """
    if worker_name not in _initialized_workers:
        # 确保日志目录存在
        worker_log_dir = LOG_DIR / worker_name
        if not worker_log_dir.exists():
            worker_log_dir.mkdir(parents=True, exist_ok=True)

        # 2. 通用日志文件 (针对特定 Worker)
        # Windows 下多进程共享日志文件会导致轮转失败，因此使用 enqueue=True 并在进程级别隔离
        logger.add(
            str(worker_log_dir / f"{worker_name}.log"),
            level="INFO",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[worker]} | {name}:{function}:{line} - {message}",
            enqueue=True,
            encoding="utf-8",
            filter=lambda record: record["extra"].get("worker") == worker_name
        )

        # 3. 错误日志文件 (针对特定 Worker)
        logger.add(
            str(worker_log_dir / f"{worker_name}_error.log"),
            level="ERROR",
            rotation="10 MB",
            retention="30 days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[worker]} | {name}:{function}:{line} - {message}",
            enqueue=True,
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            filter=lambda record: record["extra"].get("worker") == worker_name
        )
        
        _initialized_workers.add(worker_name)

    # 返回绑定了 worker 名称的 logger 实例
    return logger.bind(worker=worker_name)

# 为了保持向后兼容，保留旧的变量定义，但改为延迟初始化或按需获取
# 注意：在多进程环境下，每个进程启动时仍会导入此模块
# 我们不再在模块级别直接调用 get_worker_logger，而是让 worker 脚本显式调用
