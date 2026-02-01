"""
日志配置模块
使用 Loguru 替代标准 logging 模块，实现统一的日志管理
"""
import os
import sys
import logging
from pathlib import Path
from loguru import logger
from app.core.config import settings

# 定义日志目录
LOG_DIR = Path("logs")

class InterceptHandler(logging.Handler):
    """
    拦截标准 logging 日志并转发到 Loguru
    """
    def emit(self, record: logging.LogRecord):
        # 获取对应的 Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 获取调用者的 frame
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging():
    """
    配置日志系统
    1. 创建日志目录
    2. 配置 Loguru sink (控制台 + 文件)
    3. 拦截标准 logging
    """
    # 1. 确保日志目录存在
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 移除默认 handler
    logger.remove()

    # 3. 添加控制台输出 (带颜色)
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    # 4. 添加文件输出 (按天轮转，保留30天)
    # 普通日志
    logger.add(
        LOG_DIR / "rag_backend.log",
        level="INFO",
        rotation="00:00",  # 每天午夜轮转
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧日志
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
        encoding="utf-8"
    )

    # 错误日志单独存储
    logger.add(
        LOG_DIR / "rag_error.log",
        level="ERROR",
        rotation="10 MB",  # 按大小轮转
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
        encoding="utf-8",
        backtrace=True,
        diagnose=True
    )

    # 5. 拦截标准库日志
    # 获取所有 root logger 的 handler 并移除
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(settings.LOG_LEVEL)

    # 移除 uvicorn 和 fastapi 的默认 handlers，避免重复
    for _log in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
        _logger = logging.getLogger(_log)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False # 避免传播到 root

    logger.info(f"日志系统初始化完成，日志级别: {settings.LOG_LEVEL}")
    logger.info(f"日志文件路径: {LOG_DIR.absolute()}")

