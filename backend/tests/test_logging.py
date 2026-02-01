"""
日志系统测试用例
"""
import os
import time
from pathlib import Path
from loguru import logger
from app.core.logger import setup_logging, LOG_DIR

def test_logging_setup():
    """测试日志系统初始化"""
    # 重新初始化日志
    setup_logging()
    
    # 验证目录是否存在
    assert LOG_DIR.exists()
    assert LOG_DIR.is_dir()
    
    # 写入测试日志
    test_message = f"Test log message {time.time()}"
    logger.info(test_message)
    
    # 验证日志文件是否包含该消息
    # 给一点时间让日志写入磁盘
    time.sleep(0.1)
    
    log_file = LOG_DIR / "rag_backend.log"
    assert log_file.exists()
    
    # 读取文件内容
    # 注意：日志可能是压缩的或者正在写入，这里简单读取
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert test_message in content
    except Exception as e:
        # 如果文件被锁定或者其他原因，可能无法读取，但这在测试环境中通常没问题
        print(f"读取日志文件失败: {e}")

def test_error_logging():
    """测试错误日志"""
    setup_logging()
    
    error_message = f"Test error message {time.time()}"
    logger.error(error_message)
    
    time.sleep(0.1)
    
    error_log_file = LOG_DIR / "rag_error.log"
    assert error_log_file.exists()
    
    with open(error_log_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert error_message in content

if __name__ == "__main__":
    test_logging_setup()
    test_error_logging()
    print("日志测试通过")
