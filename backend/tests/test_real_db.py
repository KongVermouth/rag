import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.knowledge import Knowledge
from app.models.user import User
from app.core.security import create_access_token

client = TestClient(app)

@pytest.mark.asyncio
async def test_real_db_query():
    # 1. Ensure user and KB exist in real DB
    async with AsyncSessionLocal() as session:
        # Get admin user
        result = await session.execute(select(User).where(User.username == "rag_admin"))
        user = result.scalar_one_or_none()
        if not user:
            print("User rag_admin not found")
            return
        
        # Get KB 1
        result = await session.execute(select(Knowledge).where(Knowledge.id == 1))
        kb = result.scalar_one_or_none()
        if not kb:
            print("KB 1 not found")
            return
        
        print(f"DEBUG: Real DB KB1 owner={kb.user_id}, status={kb.status}")
        
        # 2. Create token for this user
        token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Call API
        response = client.get("/api/v1/knowledge/1", headers=headers)
        print(f"DEBUG: API Response status={response.status_code}, body={response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

@pytest.mark.asyncio
async def test_real_db_doc_list():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "rag_admin"))
        user = result.scalar_one_or_none()
        token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/api/v1/documents?knowledge_id=1", headers=headers)
        print(f"DEBUG: Doc List Response status={response.status_code}, body={response.text}")
        assert response.status_code == 200
