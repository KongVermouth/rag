import uuid
import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.schemas.recall import RecallTestRequest, RecallTestStatusResponse, RecallTestResultItem
from app.utils.redis_client import redis_client
from app.kafka.producer import producer
from app.services.rag_service import rag_service
from app.models.user import User

logger = logging.getLogger(__name__)

class RecallService:
    """召回测试服务类"""

    async def start_test(self, db: AsyncSession, request: RecallTestRequest, current_user: User) -> str:
        """开始召回测试任务"""
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        task_data = {
            "taskId": task_id,
            "status": "pending",
            "progress": 0.0,
            "queries_total": len(request.queries),
            "start_time": time.time(),
            "request": request.model_dump(),
            "user_id": current_user.id
        }
        await redis_client.set_recall_task(task_id, task_data)
        
        # 发送任务到 Kafka
        await producer.send("rag.recall.test", {
            "task_id": task_id,
            "queries": [q.model_dump() for q in request.queries],
            "topN": request.topN,
            "threshold": request.threshold,
            "knowledge_ids": request.knowledge_ids,
            "robot_id": request.robot_id,
            "user_id": current_user.id
        })
        
        logger.info(f"召回测试任务已启动: {task_id}, 总计 {len(request.queries)} 条查询")
        return task_id

    async def get_status(self, task_id: str) -> Optional[RecallTestStatusResponse]:
        """获取任务状态"""
        task_data = await redis_client.get_recall_task(task_id)
        if not task_data:
            return None
        
        # 计算预计剩余时间
        estimated_remaining_time = None
        if task_data["status"] == "running" and task_data["progress"] > 0:
            elapsed = time.time() - task_data["start_time"]
            total_estimated = elapsed / (task_data["progress"] / 100)
            estimated_remaining_time = max(0, total_estimated - elapsed)
            
        return RecallTestStatusResponse(
            taskId=task_id,
            status=task_data["status"],
            progress=task_data["progress"],
            estimated_remaining_time=estimated_remaining_time,
            results=task_data.get("results"),
            summary=task_data.get("summary"),
            error=task_data.get("error")
        )

    async def run_recall_task(self, db: AsyncSession, task_id: str, queries: List[Dict[str, Any]], topN: int, threshold: float, knowledge_ids: List[int], robot_id: Optional[int]):
        """执行召回测试任务的具体逻辑 (由 Worker 调用)"""
        await redis_client.update_recall_task(task_id, {"status": "running", "start_time": time.time()})
        
        results = []
        total = len(queries)
        hit_count = 0
        total_latency = 0
        
        try:
            from app.models.robot import Robot
            robot = None
            if robot_id:
                res = await db.execute(select(Robot).where(Robot.id == robot_id))
                robot = res.scalar_one_or_none()
            
            if not robot:
                # 模拟一个默认机器人配置用于检索
                from types import SimpleNamespace
                robot = SimpleNamespace(enable_rerank=False, top_k=topN)

            for i, q_data in enumerate(queries):
                query_text = q_data["query"]
                expected_ids = q_data.get("expected_doc_ids") or []
                
                start_time = time.time()
                # 执行检索
                retrieved = await rag_service.hybrid_retrieve(
                    db=db,
                    robot=robot,
                    knowledge_ids=knowledge_ids,
                    query=query_text,
                    top_k=topN
                )
                latency = time.time() - start_time
                total_latency += latency
                
                # 计算指标
                retrieved_ids = [ctx.document_id for ctx in retrieved if ctx.score >= threshold]
                
                recall = 0.0
                precision = 0.0
                f1 = 0.0
                top_n_hit = False
                
                if expected_ids:
                    hits = set(retrieved_ids) & set(expected_ids)
                    recall = len(hits) / len(expected_ids) if expected_ids else 0.0
                    precision = len(hits) / len(retrieved_ids) if retrieved_ids else 0.0
                    if recall + precision > 0:
                        f1 = 2 * (precision * recall) / (precision + recall)
                    
                    # 检查 top-N 命中 (只要任一预期文档在召回结果中)
                    top_n_hit = any(eid in [ctx.document_id for ctx in retrieved] for eid in expected_ids)
                else:
                    # 如果没有预期 ID，只要召回了结果就认为命中 (这里逻辑可根据实际需求调整)
                    top_n_hit = len(retrieved_ids) > 0
                    recall = 1.0 if top_n_hit else 0.0
                    precision = 1.0 if top_n_hit else 0.0
                    f1 = 1.0 if top_n_hit else 0.0

                if top_n_hit:
                    hit_count += 1
                
                results.append(RecallTestResultItem(
                    query=query_text,
                    recall=recall,
                    precision=precision,
                    f1=f1,
                    top_n_hit=top_n_hit,
                    retrieved_docs=[{
                        "document_id": ctx.document_id,
                        "filename": ctx.filename,
                        "score": ctx.score,
                        "content": ctx.content[:200] + "..." if len(ctx.content) > 200 else ctx.content
                    } for ctx in retrieved],
                    expected_doc_ids=expected_ids,
                    latency=latency
                ))
                
                # 更新进度
                progress = ((i + 1) / total) * 100
                if (i + 1) % 10 == 0 or (i + 1) == total:
                    await redis_client.update_recall_task(task_id, {"progress": progress})
            
            # 计算总体汇总
            summary = {
                "avg_recall": sum(r.recall for r in results) / total if total else 0,
                "avg_precision": sum(r.precision for r in results) / total if total else 0,
                "avg_f1": sum(r.f1 for r in results) / total if total else 0,
                "top_n_hit_rate": hit_count / total if total else 0,
                "avg_latency": total_latency / total if total else 0
            }
            
            await redis_client.update_recall_task(task_id, {
                "status": "finished",
                "progress": 100.0,
                "results": [r.model_dump() for r in results],
                "summary": summary
            })
            
        except Exception as e:
            logger.error(f"召回测试任务失败: {task_id}, 错误: {e}", exc_info=True)
            await redis_client.update_recall_task(task_id, {
                "status": "failed",
                "error": str(e)
            })

recall_service = RecallService()
