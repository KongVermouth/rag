from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel, Field

class LLMMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class LLMRequest(BaseModel):
    messages: List[LLMMessage]
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False
    stop: Optional[List[str]] = None
    extra_params: Dict[str, Any] = Field(default_factory=dict)

class LLMResponse(BaseModel):
    content: str
    role: str = "assistant"
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_content: Optional[str] = None
    finish_reason: Optional[str] = None
    raw_response: Dict[str, Any] = Field(default_factory=dict)

class LLMStreamChunk(BaseModel):
    content_delta: str = ""
    reasoning_delta: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None

class BaseLLMProvider(ABC):
    """LLM 厂商适配器基类"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, api_version: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.api_version = api_version

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """非流式对话接口"""
        pass

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        """流式对话接口"""
        pass

    @abstractmethod
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """向量化接口"""
        pass

    @abstractmethod
    async def rerank(self, query: str, texts: List[str], model: str, top_n: int) -> List[Dict[str, Any]]:
        """重排序接口"""
        pass

    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """计算文本的 token 数量"""
        pass
