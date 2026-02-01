import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User
from app.models.knowledge import Knowledge

client = TestClient(app)

@pytest.fixture
async def admin_token():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "rag_admin"))
        user = result.scalar_one_or_none()
        if not user:
            pytest.skip("rag_admin not found")
        token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
        return token

@pytest.mark.asyncio
async def test_get_documents_success(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Using KB 1 which we know exists
    response = client.get("/api/v1/documents?knowledge_id=1&skip=0&limit=20", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_get_documents_invalid_kb(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Using a likely non-existent KB ID
    response = client.get("/api/v1/documents?knowledge_id=999999", headers=headers)
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_documents_unauthorized():
    # No token
    response = client.get("/api/v1/documents?knowledge_id=1")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_documents_invalid_params(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Invalid skip
    response = client.get("/api/v1/documents?knowledge_id=1&skip=-1", headers=headers)
    assert response.status_code == 422
    
    # Invalid limit
    response = client.get("/api/v1/documents?knowledge_id=1&limit=101", headers=headers)
    assert response.status_code == 422
