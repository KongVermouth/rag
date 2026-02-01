import json
import logging
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.llm.base import BaseLLMProvider, LLMRequest, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude 适配器"""

    async def chat(self, request: LLMRequest) -> LLMResponse:
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version or "2023-06-01",
            "content-type": "application/json"
        }
        
        system_prompt = ""
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
            **request.extra_params
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.stop:
            payload["stop_sequences"] = request.stop

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            content = ""
            for item in data.get("content", []):
                if item.get("type") == "text":
                    content += item.get("text", "")
            
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                role="assistant",
                model=data.get("model", request.model),
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                finish_reason=data.get("stop_reason"),
                raw_response=data
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version or "2023-06-01",
            "content-type": "application/json"
        }
        
        system_prompt = ""
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
            **request.extra_params
        }
        if system_prompt:
            payload["system"] = system_prompt
        if request.stop:
            payload["stop_sequences"] = request.stop

        timeout = httpx.Timeout(timeout=120.0, connect=30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    
                    data_str = line[5:].lstrip()
                    try:
                        data = json.loads(data_str)
                        event_type = data.get("type")
                        
                        if event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield LLMStreamChunk(content_delta=delta.get("text", ""))
                        elif event_type == "message_delta":
                            yield LLMStreamChunk(
                                finish_reason=data.get("delta", {}).get("stop_reason"),
                                usage=data.get("usage")
                            )
                        elif event_type == "message_start":
                            # 可以从这里获取初始 usage
                            pass
                    except json.JSONDecodeError:
                        continue

    def get_token_count(self, text: str) -> int:
        return len(text) // 2 + (len(text.encode('utf-8')) - len(text)) // 3
