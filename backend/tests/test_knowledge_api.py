import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.models.user import User

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_knowledge_not_found():
    """测试获取不存在的知识库"""
    # Mock 认证
    with patch("app.core.deps.get_current_user") as mock_user, \
         patch("app.db.session.get_db") as mock_db, \
         patch("app.services.knowledge_service.knowledge_service.get_knowledge_by_id") as mock_get_kb:
        
        from fastapi import HTTPException
        mock_user.return_value = User(id=1, username="testuser", role="user")
        
        # 模拟 Service 抛出 404 异常
        mock_get_kb.side_effect = HTTPException(status_code=404, detail="知识库不存在")
        
        response = client.get(
            "/api/v1/knowledge/999",
            headers={"Authorization": "Bearer fake_token"}
        )
        
        # 断言状态码和统一错误格式
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404
        assert data["msg"] == "知识库不存在"

@pytest.mark.asyncio
async def test_get_knowledge_success():
    """测试成功获取知识库"""
    with patch("app.core.deps.get_current_user") as mock_user, \
         patch("app.db.session.get_db") as mock_db, \
         patch("app.services.knowledge_service.knowledge_service.get_knowledge_by_id") as mock_get_kb:
        
        from app.models.knowledge import Knowledge
        mock_user.return_value = User(id=1, username="testuser", role="user")
        
        # 模拟返回成功的知识库对象
        mock_kb = Knowledge(
            id=1,
            user_id=1,
            name="测试知识库",
            description="描述",
            embed_llm_id=1,
            vector_collection_name="test_collection",
            status=1
        )
        mock_get_kb.return_value = mock_kb
        
        response = client.get(
            "/api/v1/knowledge/1",
            headers={"Authorization": "Bearer fake_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["name"] == "测试知识库"
