import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import Document
from app.models.user import User
from app.models.knowledge import Knowledge

client = TestClient(app)

@pytest.mark.asyncio
async def test_upload_and_preview_flow():
    # Mock authentication and DB
    with patch("app.core.deps.get_current_user") as mock_user, \
         patch("app.db.session.get_db") as mock_db, \
         patch("app.services.document_service.document_service.upload_document") as mock_upload:
        
        mock_user.return_value = User(id=1, username="testuser", role="user")
        
        # Mock upload response
        mock_upload.return_value = {
            "document_id": 1,
            "filename": "test.png",
            "file_size": 1024,
            "preview_url": "/api/v1/documents/1/preview",
            "mime_type": "image/png",
            "width": 100,
            "height": 100,
            "message": "success"
        }
        
        # 1. Test Upload
        response = client.post(
            "/api/v1/documents/upload?knowledge_id=1",
            files={"file": ("test.png", b"fake image content", "image/png")},
            headers={"Authorization": "Bearer fake_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mime_type"] == "image/png"
        assert "preview_url" in data

@pytest.mark.asyncio
async def test_retrieval_test_logic():
    with patch("app.core.deps.get_current_user") as mock_user, \
         patch("app.services.robot_service.robot_service.get_robot_by_id") as mock_robot, \
         patch("app.services.robot_service.robot_service.get_robot_knowledge_ids") as mock_kbs, \
         patch("app.services.rag_service.rag_service.hybrid_retrieve") as mock_retrieve:
        
        mock_user.return_value = User(id=1, username="testuser", role="user")
        mock_robot.return_value = MagicMock(id=1, top_k=5)
        mock_kbs.return_value = [1]
        
        # Mock retrieved contexts
        from app.schemas.chat import RetrievedContext
        mock_retrieve.return_value = [
            RetrievedContext(chunk_id="c1", document_id=1, filename="f1.txt", content="content 1", score=0.9, source="vector"),
            RetrievedContext(chunk_id="c2", document_id=1, filename="f1.txt", content="content 2", score=0.5, source="keyword")
        ]
        
        # Test with threshold 0.6
        response = client.post(
            "/api/v1/robots/1/retrieval-test",
            json={"query": "test", "top_k": 5, "threshold": 0.6},
            headers={"Authorization": "Bearer fake_token"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["score"] == 0.9
        
        # Test rate limit (simulated)
        with patch("app.api.v1.robots.rate_limiter") as mock_limiter:
            mock_limiter[1] = [0] * 30 # Simulate 30 requests already made
            response = client.post(
                "/api/v1/robots/1/retrieval-test",
                json={"query": "test", "top_k": 5, "threshold": 0.0},
                headers={"Authorization": "Bearer fake_token"}
            )
            assert response.status_code == 429
            assert "限流" in response.json()["detail"]
