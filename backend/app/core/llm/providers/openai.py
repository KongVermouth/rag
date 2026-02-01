import json
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.llm.base import BaseLLMProvider, LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    """OpenAI 及兼容厂商适配器 (DeepSeek, SiliconFlow, Zhipu, etc.)"""

    async def chat(self, request: LLMRequest) -> LLMResponse:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
            **request.extra_params
        }
        if request.stop:
            payload["stop"] = request.stop

        # 针对 MiniMax 的特殊处理
        if "minimax" in url.lower() or "minimax" in request.model.lower():
            payload["tokens_to_generate"] = request.max_tokens

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            choice = data["choices"][0]
            message = choice["message"]
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=message.get("content", ""),
                role=message.get("role", "assistant"),
                model=data.get("model", request.model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                reasoning_content=message.get("reasoning_content"),
                finish_reason=choice.get("finish_reason"),
                raw_response=data
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": request.model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
            **request.extra_params
        }
        if request.stop:
            payload["stop"] = request.stop

        # 针对 MiniMax 的特殊处理
        if "minimax" in url.lower() or "minimax" in request.model.lower():
            payload["tokens_to_generate"] = request.max_tokens

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_data = await response.aread()
                    logger.error(f"OpenAI Stream Error: {response.status_code} - {error_data.decode()}")
                    response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    
                    data_str = line[5:].lstrip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            # 某些厂商可能会在 usage 中返回最后一条
                            if "usage" in data:
                                yield LLMStreamChunk(usage=data["usage"])
                            continue
                            
                        choice = choices[0]
                        delta = choice.get("delta", {})
                        
                        yield LLMStreamChunk(
                            content_delta=delta.get("content", ""),
                            reasoning_delta=delta.get("reasoning_content") or delta.get("reasoning"),
                            finish_reason=choice.get("finish_reason"),
                            usage=data.get("usage")
                        )
                    except json.JSONDecodeError:
                        continue

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        url = self.base_url or "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "input": texts
        }
        
        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            # 兼容 OpenAI 格式
            return [item["embedding"] for item in data["data"]]

    async def rerank(self, query: str, texts: List[str], model: str, top_n: int) -> List[Dict[str, Any]]:
        # OpenAI 原生不支持 rerank，但很多兼容厂商（如 SiliconFlow, Jina）支持
        # 这里尝试使用通用的 /rerank 路径
        url = self.base_url
        if not url:
             raise ValueError("Rerank requires a base_url")
             
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "query": query,
            "documents": texts,
            "top_n": top_n
        }
        
        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            # 兼容 SiliconFlow/Jina 等常见格式
            if "results" in result:
                return result["results"]
            elif "data" in result:
                return result["data"]
            return result

    def get_token_count(self, text: str) -> int:
        # 简单估算：1 token ≈ 1.5 汉字 或 4 英文单词
        # 实际生产环境建议使用 tiktoken
        return len(text) // 2 + (len(text.encode('utf-8')) - len(text)) // 3
