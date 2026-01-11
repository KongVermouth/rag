"""
导入所有模型，用于Alembic自动生成迁移脚本
"""
from app.db.session import Base
# 导入所有模型，确保它们被Base识别
# from app.models.user import User
# from app.models.llm import LLM
# from app.models.apikey import APIKey
# from app.models.knowledge import Knowledge
# from app.models.document import Document
# from app.models.robot import Robot
# from app.models.robot_knowledge import RobotKnowledge
