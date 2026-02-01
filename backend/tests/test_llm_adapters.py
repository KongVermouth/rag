import pytest
import asyncio
from app.core.llm.factory import LLMFactory
from app.core.llm.base import LLMRequest, LLMMessage

@pytest.mark.asyncio
async def test_openai_adapter_real():
    # 这是一个集成测试，需要真实的 API Key
    # 仅供演示，实际运行需设置环境变量
    import os
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("Skip: DEEPSEEK_API_KEY not set")
        
    provider = LLMFactory.get_provider(
        provider_name="deepseek",
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="你好")],
        model="deepseek-chat",
        max_tokens=10
    )
    
    response = await provider.chat(request)
    assert response.content
    assert response.total_tokens > 0
    print(f"\nResponse: {response.content}")

@pytest.mark.asyncio
async def test_openai_stream_adapter_real():
    import os
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("Skip: DEEPSEEK_API_KEY not set")
        
    provider = LLMFactory.get_provider(
        provider_name="deepseek",
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    
    request = LLMRequest(
        messages=[LLMMessage(role="user", content="你好")],
        model="deepseek-chat",
        max_tokens=10,
        stream=True
    )
    
    full_content = ""
    async for chunk in provider.chat_stream(request):
        if chunk.content_delta:
            full_content += chunk.content_delta
            
    assert full_content
    print(f"\nStream Response: {full_content}")
