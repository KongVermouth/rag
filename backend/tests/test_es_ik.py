import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.exceptions import ElasticsearchIKException

client = TestClient(app)

@pytest.mark.asyncio
async def test_es_health_check_fail():
    """测试 ES 健康检查失败场景"""
    with patch("app.utils.es_client.es_client.check_ik_analyzer", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = False
        response = client.get("/health/es")
        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"

@pytest.mark.asyncio
async def test_es_health_check_success():
    """测试 ES 健康检查成功场景"""
    with patch("app.utils.es_client.es_client.check_ik_analyzer", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = True
        response = client.get("/health/es")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

def test_global_exception_handler_ik():
    """测试全局异常处理器捕获 ElasticsearchIKException"""
    # 模拟一个会抛出 ElasticsearchIKException 的路由或逻辑
    # 这里我们直接测试异常处理器
    from app.main import es_ik_exception_handler
    from fastapi import Request
    
    exc = ElasticsearchIKException("IK 分词器缺失")
    # 模拟 request 对象
    request = AsyncMock(spec=Request)
    
    import asyncio
    response = asyncio.run(es_ik_exception_handler(request, exc))
    
    assert response.status_code == 400
    import json
    data = json.loads(response.body.decode())
    assert data["error_type"] == "illegal_argument_exception"
    assert data["msg"] == "IK 分词器缺失"
