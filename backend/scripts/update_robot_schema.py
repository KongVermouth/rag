import asyncio
import sys
import os

# 将项目根目录添加到python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine

async def update_schema():
    print("开始更新数据库模式...")
    
    async with engine.begin() as conn:
        print("检查 rag_robot 表...")
        try:
            # 检查 rerank_llm_id 是否存在
            result = await conn.execute(text("SHOW COLUMNS FROM rag_robot LIKE 'rerank_llm_id'"))
            if not result.fetchone():
                print("正在向 rag_robot 表添加缺失列: rerank_llm_id...")
                await conn.execute(text("ALTER TABLE rag_robot ADD COLUMN `rerank_llm_id` BIGINT DEFAULT NULL COMMENT '使用的重排序模型ID' AFTER `chat_llm_id`"))
            else:
                print("rag_robot 表已存在列: rerank_llm_id")
        except Exception as e:
            print(f"更新 rag_robot 表时出错: {e}")

    print("数据库模式更新完成！")

if __name__ == "__main__":
    asyncio.run(update_schema())
