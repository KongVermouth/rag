import logging
from typing import List, AsyncGenerator, Optional
from app.core.llm.base import BaseLLMProvider, LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)

class FailoverProvider(BaseLLMProvider):
    """故障转移适配器：主从切换逻辑"""
    
    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
        self.primary = primary
        self.fallback = fallback

    async def chat(self, request: LLMRequest) -> LLMResponse:
        try:
            return await self.primary.chat(request)
        except Exception as e:
            logger.warning(f"主模型调用失败，尝试切换到备用模型: {e}")
            return await self.fallback.chat(request)

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        try:
            async for chunk in self.primary.chat_stream(request):
                yield chunk
        except Exception as e:
            logger.warning(f"主模型流式调用失败，尝试切换到备用模型: {e}")
            async for chunk in self.fallback.chat_stream(request):
                yield chunk

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        try:
            return await self.primary.embed(texts, model)
        except Exception as e:
            logger.warning(f"主模型向量化失败，尝试切换到备用模型: {e}")
            return await self.fallback.embed(texts, model)

    async def rerank(self, query: str, texts: List[str], model: str, top_n: int) -> List[Dict[str, Any]]:
        try:
            return await self.primary.rerank(query, texts, model, top_n)
        except Exception as e:
            logger.warning(f"主模型重排序失败，尝试切换到备用模型: {e}")
            return await self.fallback.rerank(query, texts, model, top_n)

    def get_token_count(self, text: str) -> int:
        return self.primary.get_token_count(text)
