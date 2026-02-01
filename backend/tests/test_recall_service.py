import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from app.services.recall_service import RecallService
from app.schemas.recall import RecallTestRequest, RecallTestQuery
from app.models.user import User

@pytest.mark.asyncio
async def test_start_recall_test():
    service = RecallService()
    db = AsyncMock()
    current_user = User(id=1, username="test")
    request = RecallTestRequest(
        queries=[RecallTestQuery(query="test query")],
        knowledge_ids=[1],
        topN=10,
        threshold=0.7
    )
    
    with patch("app.services.recall_service.redis_client.set_recall_task", new_callable=AsyncMock) as mock_redis, \
         patch("app.services.recall_service.producer.send", new_callable=AsyncMock) as mock_producer:
        
        task_id = await service.start_test(db, request, current_user)
        
        assert task_id is not None
        mock_redis.assert_called_once()
        mock_producer.assert_called_once_with("rag.recall.test", ANY)

@pytest.mark.asyncio
async def test_run_recall_task_logic():
    service = RecallService()
    db = AsyncMock()
    task_id = "test-task"
    queries = [{"query": "test query", "expected_doc_ids": [1]}]
    
    mock_ctx = MagicMock()
    mock_ctx.document_id = 1
    mock_ctx.score = 0.9
    mock_ctx.filename = "test.pdf"
    mock_ctx.content = "test content"
    
    with patch("app.services.recall_service.redis_client.update_recall_task", new_callable=AsyncMock) as mock_update, \
         patch("app.services.recall_service.rag_service.hybrid_retrieve", new_callable=AsyncMock) as mock_retrieve:
        
        mock_retrieve.return_value = [mock_ctx]
        
        await service.run_recall_task(
            db=db,
            task_id=task_id,
            queries=queries,
            topN=10,
            threshold=0.7,
            knowledge_ids=[1],
            robot_id=None
        )
        
        # 验证结果更新
        # 最后一词调用应该是更新状态为 finished
        last_call = mock_update.call_args_list[-1]
        args, kwargs = last_call
        assert args[1]["status"] == "finished"
        assert args[1]["summary"]["top_n_hit_rate"] == 1.0
        assert args[1]["results"][0]["recall"] == 1.0
