import pytest
import httpx
import respx
import numpy as np
import asyncio
from app.core.llm.providers.openai import OpenAIProvider

@pytest.mark.asyncio
async def test_remote_embedding_client_success():
    url = "https://api.siliconflow.cn/v1/embeddings"
    api_key = "test_key"
    model = "BAAI/bge-large-zh-v1.5"
    
    provider = OpenAIProvider(api_key, base_url=url)
    
    mock_response = {
        "data": [
            {"embedding": [0.1, 0.2, 0.3], "index": 0},
            {"embedding": [0.4, 0.5, 0.6], "index": 1}
        ]
    }
    
    async with respx.mock:
        respx.post(url).mock(return_value=httpx.Response(200, json=mock_response))
        
        texts = ["hello", "world"]
        vectors_list = await provider.embed(texts, model)
        vectors = np.array(vectors_list)
        
        assert isinstance(vectors, np.ndarray)
        assert vectors.shape == (2, 3)
        assert np.allclose(vectors[0], [0.1, 0.2, 0.3])
