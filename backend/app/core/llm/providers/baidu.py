import json
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.llm.base import BaseLLMProvider, LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)

class BaiduProvider(BaseLLMProvider):
    """百度文心一言 (Ernie) 适配器"""

    async def _get_access_token(self) -> str:
        # 百度 API Key 实际上是 client_id:client_secret 格式，或者直接存 token
        if ":" not in self.api_key:
            return self.api_key
            
        client_id, client_secret = self.api_key.split(":")
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json().get("access_token")

    async def chat(self, request: LLMRequest) -> LLMResponse:
        access_token = await self._get_access_token()
        # 百度不同模型的 URL 不同，通常需要从配置中传入完整的 base_url
        url = self.base_url
        if not url:
             # 默认使用 ernie-4.0-8k-latest
             url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro"
             
        params = {"access_token": access_token}
        
        messages = []
        system_prompt = ""
        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "messages": messages,
            "temperature": request.temperature,
            "stream": False,
            **request.extra_params
        }
        if system_prompt:
            payload["system"] = system_prompt

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            
            if "error_code" in data:
                raise ValueError(f"Baidu API Error: {data.get('error_msg')}")
                
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=data.get("result", ""),
                role="assistant",
                model=request.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                raw_response=data
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        access_token = await self._get_access_token()
        url = self.base_url or "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro"
        params = {"access_token": access_token}
        
        messages = []
        system_prompt = ""
        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "messages": messages,
            "temperature": request.temperature,
            "stream": True,
            **request.extra_params
        }
        if system_prompt:
            payload["system"] = system_prompt

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
                        if "error_code" in data:
                            logger.error(f"Baidu Stream Error: {data.get('error_msg')}")
                            break
                            
                        yield LLMStreamChunk(
                            content_delta=data.get("result", ""),
                            finish_reason="stop" if data.get("is_end") else None,
                            usage=data.get("usage")
                        )
                    except json.JSONDecodeError:
                        continue

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        # 百度 Embedding 接口
        access_token = await self._get_access_token()
        url = self.base_url or "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/embeddings/embedding-v1"
        params = {"access_token": access_token}
        
        payload = {"input": texts}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    async def rerank(self, query: str, texts: List[str], model: str, top_n: int) -> List[Dict[str, Any]]:
        raise NotImplementedError("Baidu native rerank not implemented in this adapter yet.")

    def get_token_count(self, text: str) -> int:
        return len(text) // 2 + (len(text.encode('utf-8')) - len(text)) // 3
