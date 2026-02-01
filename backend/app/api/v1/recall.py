from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.recall import RecallTestRequest, RecallTestStatusResponse
from app.services.recall_service import recall_service

router = APIRouter()

@router.post("/test", summary="提交召回测试任务")
async def start_recall_test(
    request: RecallTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交批量召回测试任务，返回任务ID
    """
    if not request.queries:
        raise HTTPException(status_code=400, detail="查询列表不能为空")
    
    if len(request.queries) > 5000:
        raise HTTPException(status_code=400, detail="单次最多支持5000条提问词")
        
    task_id = await recall_service.start_test(db, request, current_user)
    return {"taskId": task_id}

@router.get("/status/{task_id}", response_model=RecallTestStatusResponse, summary="获取召回测试状态")
async def get_recall_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    获取任务状态及结果
    """
    status_info = await recall_service.get_status(task_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
        
    return status_info
