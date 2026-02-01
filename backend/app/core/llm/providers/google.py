import json
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.llm.base import BaseLLMProvider, LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)

class GoogleProvider(BaseLLMProvider):
    """Google Gemini 适配器"""

    async def chat(self, request: LLMRequest) -> LLMResponse:
        model_name = request.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            
        url = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
        params = {"key": self.api_key}
        
        contents = []
        for msg in request.messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                **request.extra_params
            }
        }

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError(f"Gemini API returned no candidates: {data}")
                
            candidate = candidates[0]
            content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
            usage = data.get("usageMetadata", {})
            
            return LLMResponse(
                content=content,
                role="assistant",
                model=request.model,
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
                finish_reason=candidate.get("finishReason"),
                raw_response=data
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        model_name = request.model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            
        url = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/{model_name}:streamGenerateContent"
        params = {"key": self.api_key, "alt": "sse"}
        
        contents = []
        for msg in request.messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                **request.extra_params
            }
        }

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, params=params) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    
                    data_str = line[5:].lstrip()
                    try:
                        data = json.loads(data_str)
                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue
                            
                        candidate = candidates[0]
                        parts = candidate.get("content", {}).get("parts", [])
                        if parts:
                            yield LLMStreamChunk(
                                content_delta=parts[0].get("text", ""),
                                finish_reason=candidate.get("finishReason")
                            )
                        
                        usage = data.get("usageMetadata")
                        if usage:
                            yield LLMStreamChunk(usage={
                                "prompt_tokens": usage.get("promptTokenCount", 0),
                                "completion_tokens": usage.get("candidatesTokenCount", 0),
                                "total_tokens": usage.get("totalTokenCount", 0)
                            })
                    except json.JSONDecodeError:
                        continue

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # Google Gemini Embedding API
        if not model.startswith("models/"):
            model = f"models/{model}"
            
        url = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/{model}:batchEmbedContents"
        params = {"key": self.api_key}
        
        payload = {
            "requests": [{"model": model, "content": {"parts": [{"text": t}]}} for t in texts]
        }
        
        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            return [item["values"] for item in data["embeddings"]]

    async def rerank(self, query: str, texts: List[str], model: str, top_n: int) -> List[Dict[str, Any]]:
        # Google 目前没有原生的 Rerank API，通常通过调用 LLM 比较或使用其他服务
        raise NotImplementedError("Google Gemini does not provide a native Rerank API yet.")

    def get_token_count(self, text: str) -> int:
        return len(text) // 2 + (len(text.encode('utf-8')) - len(text)) // 3
