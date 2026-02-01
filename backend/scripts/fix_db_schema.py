import asyncio
import sys
import os

# 将项目根目录添加到python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine

async def fix_schema():
    print("开始修复数据库模式...")
    
    async with engine.begin() as conn:
        # 1. 修复 rag_knowledge 表的列名
        print("检查 rag_knowledge 表...")
        try:
            # 检查是否存在带空格的列名 'document count'
            result = await conn.execute(text("SHOW COLUMNS FROM rag_knowledge LIKE 'document count'"))
            if result.fetchone():
                print("发现 rag_knowledge 表中存在 'document count' 列，正在重命名为 'document_count'...")
                await conn.execute(text("ALTER TABLE rag_knowledge CHANGE `document count` `document_count` INT DEFAULT 0 COMMENT '文档数量'"))
            else:
                print("rag_knowledge 表中未发现 'document count' 列，无需修复。")
        except Exception as e:
            print(f"检查/修复 rag_knowledge 表时出错: {e}")

        # 2. 修复 rag_robot 表
        print("检查 rag_robot 表...")
        try:
            # 检查 llm_id 是否存在，如果是则重命名为 chat_llm_id
            result = await conn.execute(text("SHOW COLUMNS FROM rag_robot LIKE 'llm_id'"))
            if result.fetchone():
                print("发现 rag_robot 表中存在 'llm_id' 列，正在重命名为 'chat_llm_id'...")
                await conn.execute(text("ALTER TABLE rag_robot CHANGE `llm_id` `chat_llm_id` BIGINT NOT NULL COMMENT '使用的对话模型ID'"))
            
            # 检查并添加缺失的列
            columns_to_add = [
                ("description", "VARCHAR(500) DEFAULT NULL COMMENT '机器人描述'"),
                ("enable_rerank", "TINYINT(1) DEFAULT 0 COMMENT '是否启用重排序'"),
                ("temperature", "FLOAT DEFAULT 0.7 COMMENT '生成温度'"),
                ("max_tokens", "INT DEFAULT 2000 COMMENT '最大生成Token数'")
            ]
            
            for col_name, col_def in columns_to_add:
                result = await conn.execute(text(f"SHOW COLUMNS FROM rag_robot LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"正在向 rag_robot 表添加缺失列: {col_name}...")
                    await conn.execute(text(f"ALTER TABLE rag_robot ADD COLUMN `{col_name}` {col_def}"))
                else:
                    print(f"rag_robot 表已存在列: {col_name}")
                    
        except Exception as e:
            print(f"检查/修复 rag_robot 表时出错: {e}")

        # 3. 修复 rag_document 表
        print("检查 rag_document 表...")
        try:
            columns_to_add = [
                ("mime_type", "VARCHAR(100) DEFAULT NULL COMMENT '文件MIME类型'"),
                ("width", "INT DEFAULT NULL COMMENT '宽度(图片/视频)'"),
                ("height", "INT DEFAULT NULL COMMENT '高度(图片/视频)'")
            ]
            
            for col_name, col_def in columns_to_add:
                result = await conn.execute(text(f"SHOW COLUMNS FROM rag_document LIKE '{col_name}'"))
                if not result.fetchone():
                    print(f"正在向 rag_document 表添加缺失列: {col_name}...")
                    await conn.execute(text(f"ALTER TABLE rag_document ADD COLUMN `{col_name}` {col_def}"))
                else:
                    print(f"rag_document 表已存在列: {col_name}")
                    
        except Exception as e:
            print(f"检查/修复 rag_document 表时出错: {e}")

    print("数据库模式修复完成！")

if __name__ == "__main__":
    asyncio.run(fix_schema())
