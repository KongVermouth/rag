import os
import pytest
from pathlib import Path
from app.core.worker_logger import setup_worker_logger

def test_worker_logger_creation():
    """验证能够为不同 worker 创建独立的日志目录和文件"""
    worker_name = "test_worker"
    log_dir = Path("logs/workers") / worker_name
    
    # 清理旧的测试日志
    if log_dir.exists():
        for f in log_dir.iterdir():
            f.unlink()
    
    # 初始化 logger
    test_logger = setup_worker_logger(worker_name)
    
    # 记录不同级别的日志
    test_logger.info("这是一条测试 INFO 日志")
    test_logger.error("这是一条测试 ERROR 日志")
    
    # 检查目录是否创建
    assert log_dir.exists()
    
    # 检查文件是否生成
    # 注意：loguru 的写入可能是异步或带缓存的，但在 enqueue=True 模式下通常很快
    import time
    time.sleep(1) # 等待写入
    
    log_file = log_dir / f"{worker_name}.log"
    error_file = log_dir / f"{worker_name}_error.log"
    
    assert log_file.exists()
    assert error_file.exists()
    
    # 验证内容
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "这是一条测试 INFO 日志" in content
        assert "INFO" in content

    with open(error_file, "r", encoding="utf-8") as f:
        content = f.read()
        assert "这是一条测试 ERROR 日志" in content
        assert "ERROR" in content

if __name__ == "__main__":
    pytest.main([__file__])
