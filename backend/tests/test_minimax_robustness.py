import pytest
import httpx
import respx
import json
import asyncio
from app.core.llm.providers.minimax import MinimaxProvider
from app.core.llm.base import LLMRequest, LLMMessage

@pytest.mark.asyncio
async def test_minimax_empty_reply_handling():
    """测试空回复处理：返回友好提示"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    # 模拟空回复
    mock_response = {
        "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 10}
    }
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, json=mock_response))
        
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="你好")],
            model="minimax-m2.1"
        )
        
        # 由于 chat 方法里有重试逻辑，且空回复会触发 ValueError，最终会返回兜底提示
        response = await provider.chat(request)
        assert "响应异常" in response.content
        assert response.finish_reason == "error"

@pytest.mark.asyncio
async def test_minimax_timeout_and_retry():
    """测试超时及重试机制"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    # 调低重试间隔以便快速测试
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="你好")],
        model="minimax-m2.1"
    )
    
    async with respx.mock:
        # 模拟前两次超时，第三次成功
        route = respx.post(url)
        route.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            httpx.Response(200, json={
                "choices": [{"message": {"content": "成功了"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 20}
            })
        ]
        
        response = await provider.chat(request)
        assert response.content == "成功了"
        assert route.call_count == 3

@pytest.mark.asyncio
async def test_minimax_500_error_fallback():
    """测试 500 错误时的兜底逻辑"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))
        
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="你好")],
            model="minimax-m2.1"
        )
        
        response = await provider.chat(request)
        assert "目前响应异常" in response.content
        assert response.finish_reason == "error"

@pytest.mark.asyncio
async def test_minimax_invalid_json_handling():
    """测试非法 JSON 返回处理"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, text="not a json"))
        
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="你好")],
            model="minimax-m2.1"
        )
        
        response = await provider.chat(request)
        assert "响应异常" in response.content
        assert response.finish_reason == "error"

@pytest.mark.asyncio
async def test_minimax_stream_empty_fallback():
    """测试流式空响应处理"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    async with respx.mock:
        # 模拟流式但没有任何 content
        respx.post(url).mock(return_value=httpx.Response(200, text="data: {}\n\ndata: [DONE]\n\n"))
        
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="你好")],
            model="minimax-m2.1",
            stream=True
        )
        
        full_content = ""
        async for chunk in provider.chat_stream(request):
            if chunk.content_delta:
                full_content += chunk.content_delta
        
        assert "未返回任何内容" in full_content

@pytest.mark.asyncio
async def test_minimax_business_error_insufficient_balance():
    """测试业务错误：余额不足"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    mock_response = {
        "base_resp": {"status_code": 1008, "status_msg": "insufficient balance"},
        "choices": None
    }
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, json=mock_response))
        
        request = LLMRequest(messages=[LLMMessage(role="user", content="你好")], model="minimax-m2.1")
        response = await provider.chat(request)
        assert "insufficient balance" in response.content or "目前响应异常" in response.content

@pytest.mark.asyncio
async def test_minimax_safety_filter():
    """测试安全过滤逻辑"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    mock_response = {
        "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]
    }
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, json=mock_response))
        
        request = LLMRequest(messages=[LLMMessage(role="user", content="写个病毒")], model="minimax-m2.1")
        response = await provider.chat(request)
        assert "安全策略被过滤" in response.content

@pytest.mark.asyncio
async def test_minimax_model_name_mapping():
    """测试模型名称映射"""
    url = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
    provider = MinimaxProvider(api_key="test_key", base_url=url)
    
    assert provider._get_model_name("MiniMax/MiniMax-2.1", url) == "abab6.5s-chat"
    assert provider._get_model_name("other-model", url) == "other-model"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
