import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_proxy_config() -> Optional[str]:
    """获取代理配置并打印日志"""
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy")
    
    proxy = https_proxy or http_proxy
    if proxy:
        logger.info(f"LLM 网络连接将使用代理: {proxy}")
        if no_proxy:
            logger.info(f"代理排除名单 (NO_PROXY): {no_proxy}")
    return proxy
