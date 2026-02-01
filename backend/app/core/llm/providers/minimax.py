import json
import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.llm.base import LLMRequest, LLMResponse, LLMStreamChunk
from app.core.llm.providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)

class MinimaxProvider(OpenAIProvider):
    """MiniMax 专用适配器，具备增强的鲁棒性处理"""

    def _get_model_name(self, model: str, url: str) -> str:
        """模型名称映射，兼容一些常见的错误配置"""
        if "minimaxi.com" in url:
            # 如果是官方 API，映射一些常见的别名
            mapping = {
                "minimax-2.1": "abab6.5s-chat",
                "minimax-m2.1": "abab6.5s-chat",
                "minimax/minimax-2.1": "abab6.5s-chat",
                "abab6.5": "abab6.5s-chat",
            }
            return mapping.get(model.lower(), model)
        return model

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """增强版的非流式对话，支持超时、重试、非空校验及兜底"""
        from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type
        
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, ValueError)),
                reraise=True
            ):
                with attempt:
                    return await self._chat_internal(request)
        except Exception as e:
            logger.error(f"MiniMax 调用最终失败: {str(e)}")
            return LLMResponse(
                content="抱歉，MiniMax 模型目前响应异常，请稍后再试或联系管理员。",
                role="assistant",
                model=request.model,
                finish_reason="error"
            )

    async def _chat_internal(self, request: LLMRequest) -> LLMResponse:
        """内部调用逻辑，供 chat 方法进行重试包装"""
        url = self.base_url or "https://api.minimaxi.com/v1/text/chatcompletion_v2"
        model_name = self._get_model_name(request.model, url)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_name,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "tokens_to_generate": request.max_tokens,
            "stream": False,
            **request.extra_params
        }
        if request.stop:
            payload["stop"] = request.stop
        
        timeout = httpx.Timeout(timeout=30.0, connect=5.0, read=25.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"MiniMax API Error Snapshot [Status={response.status_code}]: {response.text}")
                response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error(f"MiniMax Invalid JSON Snapshot: {response.text}")
                raise ValueError("MiniMax 返回非法的 JSON 格式")
            
            # 业务错误检查
            if "base_resp" in data and data["base_resp"].get("status_code") != 0:
                error_msg = data["base_resp"].get("status_msg", "未知业务错误")
                logger.error(f"MiniMax API Business Error: {error_msg}")
                raise ValueError(f"MiniMax 业务错误: {error_msg}")

            if not data or "choices" not in data or not data["choices"]:
                logger.error(f"MiniMax Structure Error Snapshot: {json.dumps(data)}")
                raise ValueError("MiniMax 响应结构异常: choices 为空")
            
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            finish_reason = choice.get("finish_reason")

            if not content or len(content.strip()) == 0:
                if finish_reason == "content_filter":
                    return LLMResponse(
                        content="[内容因安全策略被过滤]",
                        role="assistant",
                        model=data.get("model", request.model),
                        finish_reason=finish_reason,
                        raw_response=data
                    )
                logger.error(f"MiniMax Empty Content Snapshot: {json.dumps(data)}")
                raise ValueError("MiniMax 回复内容为空")

            usage = data.get("usage", {})
            return LLMResponse(
                content=content,
                role=message.get("role", "assistant"),
                model=data.get("model", request.model),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                finish_reason=choice.get("finish_reason"),
                raw_response=data
            )

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMStreamChunk, None]:
        """增强版的流式对话，支持超时监控、错误识别与非空校验"""
        url = self.base_url or "https://api.minimaxi.com/v1/text/chatcompletion_v2"
        model_name = self._get_model_name(request.model, url)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 参数映射优化
        payload = {
            "model": model_name,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": max(0.01, request.temperature), # MiniMax temperature usually > 0
            "max_tokens": request.max_tokens,
            "tokens_to_generate": request.max_tokens,
            "stream": True,
            **request.extra_params
        }
        if request.stop:
            payload["stop"] = request.stop

        timeout = httpx.Timeout(timeout=45.0, connect=5.0, read=15.0)
        
        has_content = False
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    # 检查是否返回了 JSON 错误（有些厂商在 stream=True 时也会返回 200 OK 但内容是 JSON 错误）
                    if response.status_code == 200:
                        first_line = await response.aiter_lines().__anext__()
                        if first_line.startswith('{'):
                            try:
                                data = json.loads(first_line)
                                if "base_resp" in data and data["base_resp"].get("status_code") != 0:
                                    error_msg = data["base_resp"].get("status_msg", "未知错误")
                                    logger.error(f"MiniMax API Business Error: {error_msg}")
                                    yield LLMStreamChunk(content_delta=f"模型调用失败: {error_msg}")
                                    return
                            except:
                                pass
                        
                        # 如果不是错误，我们需要重新处理这一行（如果有的话）
                        # 这里比较麻烦，因为 aiter_lines 不支持回退。
                        # 简单起见，我们重新发起请求或者在循环中处理。
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(f"MiniMax Stream Error Snapshot [Status={response.status_code}]: {error_text.decode()}")
                        yield LLMStreamChunk(content_delta=f"抱歉，模型服务异常 (状态码 {response.status_code})。")
                        return

                    # 重新获取流以处理所有行
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            
                            # 处理非 data: 开头的 JSON 错误行
                            if line.startswith('{'):
                                try:
                                    data = json.loads(line)
                                    if "base_resp" in data and data["base_resp"].get("status_code") != 0:
                                        error_msg = data["base_resp"].get("status_msg", "参数或模型错误")
                                        yield LLMStreamChunk(content_delta=f"模型回复异常: {error_msg}")
                                        return
                                except:
                                    pass

                            if not line.startswith("data:"):
                                continue
                            
                            data_str = line[5:].lstrip()
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if not choices:
                                    # 检查是否有 usage
                                    if "usage" in data:
                                        yield LLMStreamChunk(usage=data["usage"])
                                    continue
                                    
                                choice = choices[0]
                                delta = choice.get("delta", {})
                                content_delta = delta.get("content", "")
                                finish_reason = choice.get("finish_reason")
                                
                                if content_delta:
                                    has_content = True
                                    yield LLMStreamChunk(
                                        content_delta=content_delta,
                                        finish_reason=finish_reason,
                                        usage=data.get("usage")
                                    )
                                elif finish_reason == "content_filter":
                                    yield LLMStreamChunk(content_delta="[内容因安全策略被过滤]")
                                    has_content = True
                            except json.JSONDecodeError:
                                continue

            if not has_content:
                logger.error("MiniMax Stream yielded no content")
                yield LLMStreamChunk(content_delta="[模型未返回任何内容，请尝试更换问题或模型]")

        except Exception as e:
            logger.error(f"MiniMax Stream 发生异常: {str(e)}")
            if not has_content:
                yield LLMStreamChunk(content_delta=f"抱歉，模型流式响应发生异常: {str(e)}")
