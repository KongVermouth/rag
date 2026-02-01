from typing import Dict, Type, Optional
from app.core.llm.base import BaseLLMProvider
from app.core.llm.providers.openai import OpenAIProvider
from app.core.llm.providers.anthropic import AnthropicProvider
from app.core.llm.providers.google import GoogleProvider
from app.core.llm.providers.baidu import BaiduProvider
from app.core.llm.providers.minimax import MinimaxProvider

class LLMFactory:
    """LLM 厂商适配器工厂"""
    
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "deepseek": OpenAIProvider,
        "siliconflow": OpenAIProvider,
        "minimax": MinimaxProvider,
        "moonshot": OpenAIProvider,
        "zhipu": OpenAIProvider,
        "qwen": OpenAIProvider,
        "baichuan": OpenAIProvider,
        "yi": OpenAIProvider,
        "doubao": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "gemini": GoogleProvider,
        "baidu": BaiduProvider,
        "ernie": BaiduProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get_provider(
        cls, 
        provider_name: str, 
        api_key: str, 
        base_url: Optional[str] = None, 
        api_version: Optional[str] = None
    ) -> BaseLLMProvider:
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            # 默认使用 OpenAI 兼容模式
            logger.warning(f"未找到厂商 {provider_name} 的专用适配器，尝试使用 OpenAI 兼容模式")
            provider_class = OpenAIProvider
            
        return provider_class(api_key=api_key, base_url=base_url, api_version=api_version)

import logging
logger = logging.getLogger(__name__)
