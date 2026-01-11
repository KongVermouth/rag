# RAG 后端系统

企业级 RAG（检索增强生成）知识问答系统后端服务，支持多用户、多知识库、多机器人的管理与问答能力，并提供完整的会话管理与多轮对话上下文管理功能。

## 技术栈

- **Web框架**: Python 3.10 + FastAPI
- **数据库**: MySQL 8.0
- **向量检索**: Milvus 2.4.10
- **全文检索**: Elasticsearch 7.17.10
- **缓存/上下文**: Redis 7.2
- **Embedding模型**: Qwen3-Embedding-0.6B
- **异步任务**: Celery + Redis
- **文档解析**: PyMuPDF, python-docx, html2text

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                     │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP / WebSocket
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Server                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ API Layer (app/api/v1/)                                  │ │
│  │  - auth.py      - users.py     - llms.py                 │ │
│  │  - apikeys.py   - knowledge.py - documents.py            │ │
│  │  - robots.py    - chat.py                               │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Service Layer (app/services/)                            │ │
│  │  - auth_service       - user_service      - llm_service  │ │
│  │  - knowledge_service  - document_service  - robot_service│ │
│  │  - rag_service        - session_service   - context_mgr  │ │
│  └─────────────────────────────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────┐
│    MySQL     │   │  Elasticsearch   │   │   Milvus     │
│  (元数据/用户 │   │   (关键词检索)   │   │  (向量检索)  │
│   会话/历史)  │   │                  │   │              │
└──────────────┘   └──────────────────┘   └──────────────┘
        │
        ▼
┌──────────────┐
│    Redis     │
│  (会话缓存/   │
│   上下文管理) │
└──────────────┘
```

## 项目结构

```
backend/
├── app/                                    # 应用主目录
│   ├── api/v1/                            # API路由层
│   │   ├── __init__.py                    # 路由聚合器
│   │   ├── auth.py                        # 认证接口
│   │   ├── users.py                       # 用户管理
│   │   ├── llms.py                        # LLM模型管理
│   │   ├── apikeys.py                     # API密钥管理
│   │   ├── knowledge.py                   # 知识库管理
│   │   ├── documents.py                   # 文档管理
│   │   ├── robots.py                      # 机器人管理
│   │   └── chat.py                        # 对话问答
│   │
│   ├── core/                              # 核心配置
│   │   ├── config.py                      # 系统配置
│   │   ├── security.py                    # 安全模块(JWT/AES)
│   │   └── deps.py                        # 依赖注入
│   │
│   ├── db/                                # 数据库
│   │   ├── base.py                        # 模型基类
│   │   └── session.py                     # 数据库会话
│   │
│   ├── models/                            # SQLAlchemy数据模型
│   │   ├── user.py                        # 用户模型
│   │   ├── llm.py                         # LLM模型
│   │   ├── apikey.py                      # API Key
│   │   ├── knowledge.py                   # 知识库
│   │   ├── document.py                    # 文档
│   │   ├── robot.py                       # 机器人
│   │   ├── robot_knowledge.py             # 机器人-知识库关联
│   │   ├── session.py                     # 会话
│   │   └── chat_history.py                # 聊天历史
│   │
│   ├── schemas/                           # Pydantic数据验证
│   │   ├── user.py
│   │   ├── llm.py
│   │   ├── apikey.py
│   │   ├── knowledge.py
│   │   ├── document.py
│   │   ├── robot.py
│   │   └── chat.py
│   │
│   ├── services/                          # 业务逻辑层
│   │   ├── auth_service.py                # 认证服务
│   │   ├── user_service.py                # 用户服务
│   │   ├── llm_service.py                 # LLM服务
│   │   ├── apikey_service.py              # API Key服务
│   │   ├── knowledge_service.py           # 知识库服务
│   │   ├── document_service.py            # 文档服务
│   │   ├── robot_service.py               # 机器人服务
│   │   ├── rag_service.py                 # RAG核心服务
│   │   ├── session_service.py             # 会话服务
│   │   └── context_manager.py             # 上下文管理
│   │
│   ├── tasks/                             # Celery异步任务
│   │   ├── __init__.py
│   │   ├── celery_app.py                  # Celery配置
│   │   └── document_tasks.py              # 文档处理任务
│   │
│   ├── utils/                             # 工具函数
│   │   ├── embedding.py                   # 向量化工具
│   │   ├── es_client.py                   # Elasticsearch客户端
│   │   ├── file_parser.py                 # 文件解析
│   │   ├── milvus_client.py               # Milvus客户端
│   │   ├── redis_client.py                # Redis客户端
│   │   ├── storage.py                     # 文件存储
│   │   └── text_splitter.py               # 文本切片
│   │
│   └── main.py                            # FastAPI应用入口
│
├── data/                                  # 数据目录
│   └── cleaned_md/                        # 清理后的文档
│
├── models/                                # Embedding模型目录
│   └── Qwen/Qwen3-Embedding-0___6B/
│
├── .env                                   # 环境变量
├── .env.example                           # 环境配置模板
├── pyproject.toml                         # 项目配置
└── readme.md                              # 项目说明
```

## API 接口文档

### 1. 认证模块 `/api/v1/auth`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/auth/register` | POST | 用户注册 |
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/auth/me` | GET | 获取当前用户信息 |
| `/api/v1/auth/refresh` | POST | 刷新Token |

### 2. 用户管理 `/api/v1/users`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/users` | GET | 获取用户列表 |
| `/api/v1/users` | POST | 创建用户 |
| `/api/v1/users/{id}` | GET | 获取用户详情 |
| `/api/v1/users/{id}` | PUT | 更新用户 |
| `/api/v1/users/{id}` | DELETE | 删除用户 |

### 3. LLM模型管理 `/api/v1/llms`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/llms` | GET | 获取模型列表 |
| `/api/v1/llms` | POST | 创建模型配置 |
| `/api/v1/llms/{id}` | GET | 获取模型详情 |
| `/api/v1/llms/{id}` | PUT | 更新模型配置 |
| `/api/v1/llms/{id}` | DELETE | 删除模型配置 |

### 4. API密钥管理 `/api/v1/apikeys`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/apikeys` | GET | 获取密钥列表 |
| `/api/v1/apikeys` | POST | 创建API密钥 |
| `/api/v1/apikeys/{id}` | DELETE | 删除API密钥 |

### 5. 知识库管理 `/api/v1/knowledge`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/knowledge` | GET | 获取知识库列表 |
| `/api/v1/knowledge` | POST | 创建知识库 |
| `/api/v1/knowledge/{id}` | GET | 获取知识库详情 |
| `/api/v1/knowledge/{id}` | PUT | 更新知识库 |
| `/api/v1/knowledge/{id}` | DELETE | 删除知识库 |

### 6. 文档管理 `/api/v1/documents`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/documents` | GET | 获取文档列表 |
| `/api/v1/documents` | POST | 上传文档 |
| `/api/v1/documents/{id}` | GET | 获取文档详情 |
| `/api/v1/documents/{id}` | DELETE | 删除文档 |
| `/api/v1/documents/{id}/reprocess` | POST | 重新处理文档 |

### 7. 机器人管理 `/api/v1/robots`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/robots` | GET | 获取机器人列表 |
| `/api/v1/robots` | POST | 创建机器人 |
| `/api/v1/robots/{id}` | GET | 获取机器人详情 |
| `/api/v1/robots/{id}` | PUT | 更新机器人 |
| `/api/v1/robots/{id}` | DELETE | 删除机器人 |
| `/api/v1/robots/{id}/knowledge` | GET | 获取机器人关联的知识库 |
| `/api/v1/robots/{id}/knowledge` | POST | 关联知识库到机器人 |
| `/api/v1/robots/{id}/knowledge/{kid}` | DELETE | 移除知识库关联 |

### 8. 对话问答 `/api/v1/chat` (核心模块)

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/chat/ask` | POST | 对话问答(支持多轮对话) |
| `/api/v1/chat/test` | POST | 测试知识库检索效果 |
| `/api/v1/chat/sessions` | POST | 创建新会话 |
| `/api/v1/chat/sessions` | GET | 获取会话列表 |
| `/api/v1/chat/sessions/{id}` | GET | 获取会话详情 |
| `/api/v1/chat/sessions/{id}` | PUT | 更新会话 |
| `/api/v1/chat/sessions/{id}` | DELETE | 删除会话 |
| `/api/v1/chat/history/{id}` | GET | 获取会话历史 |
| `/api/v1/chat/feedback` | POST | 提交消息反馈 |

### 9. 健康检查 `/api/v1/health`

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |

## 快速开始

### 1. 环境准备

**系统要求**：
- Python 3.10 - 3.12
- Docker 和 Docker Compose
- Git

### 2. 启动依赖服务

使用 Docker Compose 启动 MySQL、Elasticsearch、Milvus、Redis 等服务：

```bash
docker-compose up -d
```

等待服务启动完成（约1-2分钟），可以通过以下命令检查服务状态：

```bash
docker-compose ps
```

### 3. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4. 配置环境变量

复制环境配置模板并修改：

```bash
cp .env.example .env
```

编辑 `.env` 文件，修改以下关键配置：
- `JWT_SECRET_KEY`: 修改为随机字符串（至少32字符）
- `AES_ENCRYPTION_KEY`: 修改为32字节随机字符串
- 其他配置根据实际情况调整

### 5. 初始化数据库

执行数据库 DDL 脚本：

```bash
# 方式1：使用MySQL客户端
mysql -h localhost -u root -proot < sql/ddl.txt

# 方式2：使用docker exec
docker exec -i rag-mysql8 mysql -u root -proot < sql/ddl.txt
```

### 6. 安装 Elasticsearch IK 分词器

```bash
# 在 ES 容器中安装 IK 分词器
docker exec -it rag-es7 elasticsearch-plugin install https://github.com/infinilabs/analysis-ik/releases/download/v7.17.10/elasticsearch-analysis-ik-7.17.10.zip

# 重启 ES 容器使插件生效
docker restart rag-es7
```

### 7. 启动应用

**启动 FastAPI 服务**：

```bash
# 开发模式（支持热重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**启动 Celery Worker**（新终端）：

```bash
celery -A app.tasks.celery_app worker --loglevel=info -Q document_processing
```

### 8. 访问 API 文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 9. 测试接口

```bash
curl http://localhost:8000/api/v1/health
```

## 核心功能

### 用户认证与管理
- 用户注册、登录（JWT认证）
- 用户信息管理
- 角色权限控制（Admin/User）

### 知识库管理
- 创建/查询/修改/删除知识库
- 配置 Embedding 模型
- 文档切片参数配置

### 文档管理
- 上传文档（PDF/DOCX/MD/HTML/TXT）
- 异步文档解析与向量化
- 文档状态跟踪
- 文档删除与重新处理

### 机器人配置
- 创建/配置问答机器人
- 关联知识库
- 配置检索参数（top_k、相似度阈值）
- 配置 Prompt 模板

### RAG 问答服务
- 混合检索（向量检索 + BM25关键词检索）
- RRF 融合排序
- 多轮对话上下文支持
- 引用来源追踪

### 会话管理
- 用户会话创建/查询/更新/删除
- 会话历史记录持久化
- 会话置顶/归档功能
- 用户反馈系统

### 上下文管理
- Redis 热数据缓存
- 最多10轮对话上下文限制
- 上下文自动过期清理
- 会话锁防止并发冲突

### LLM 模型管理
- 配置多种 LLM 模型
- API Key 加密存储
- 模型类型区分（Chat/Embedding/Rerank）

## 数据库表结构

| 表名 | 描述 |
|------|------|
| `rag_user` | 用户表 |
| `rag_llm` | 大模型定义表 |
| `rag_apikey` | API Key管理表 |
| `rag_knowledge` | 知识库表 |
| `rag_document` | 文档表 |
| `rag_robot` | 问答机器人表 |
| `rag_robot_knowledge` | 机器人-知识库关联表 |
| `rag_session` | 用户会话表 |
| `rag_chat_history` | 历史问答记录表 |

## Redis 数据结构

| Key模式 | 类型 | 描述 | TTL |
|---------|------|------|-----|
| `rag:session:{id}:context` | Hash | 会话上下文元数据 | 2小时 |
| `rag:session:{id}:messages` | List | 对话历史消息 | 2小时 |
| `rag:user:{id}:active_sessions` | Sorted Set | 用户活跃会话 | 24小时 |
| `rag:session:{id}:lock` | String | 会话锁 | 30秒 |

## 常见问题

### 1. Elasticsearch 连接失败

确保 Elasticsearch 服务已启动并安装 IK 分词器：

```bash
curl http://localhost:9200
```

### 2. Milvus 集合创建失败

检查 Milvus 服务状态：

```bash
docker-compose logs milvus-standalone
```

### 3. Celery 任务执行失败

查看 Celery Worker 日志：

```bash
celery -A app.tasks.celery_app worker --loglevel=debug
```

### 4. 文档解析失败

检查文件格式是否支持，查看错误日志中的详细信息。

### 5. Redis 连接失败

检查 Redis 服务状态：

```bash
docker-compose logs redis
```

## 部署

### Docker 部署

构建镜像：

```bash
docker build -t rag-backend:latest .
```

运行容器：

```bash
docker run -d \
  --name rag-backend \
  -p 8000:8000 \
  --env-file .env \
  rag-backend:latest
```

### 生产环境建议

- 使用 Nginx 作为反向代理
- 启用 HTTPS
- 配置日志收集（ELK Stack）
- 设置监控告警（Prometheus + Grafana）
- 配置备份策略

## 许可证

MIT License

## 参与贡献

欢迎提交 Issue 和 Pull Request！

---

**更新日志**

- 2026-01-11: 更新文档，添加完整API接口列表和项目架构
