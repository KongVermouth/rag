from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

class RecallTestQuery(BaseModel):
    query: str
    expected_doc_ids: Optional[List[int]] = None

class RecallTestRequest(BaseModel):
    queries: List[RecallTestQuery]
    topN: int = Field(default=10, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    knowledge_ids: List[int] = Field(..., description="指定测试的知识库ID列表")
    robot_id: Optional[int] = None

class RecallTestResultItem(BaseModel):
    query: str
    recall: float
    precision: float
    f1: float
    top_n_hit: bool
    retrieved_docs: List[Dict[str, Any]]
    expected_doc_ids: Optional[List[int]] = None
    latency: float

class RecallTestStatusResponse(BaseModel):
    taskId: str
    status: str  # pending, running, finished, failed
    progress: float
    estimated_remaining_time: Optional[float] = None
    results: Optional[List[RecallTestResultItem]] = None
    summary: Optional[Dict[str, float]] = None
    error: Optional[str] = None
