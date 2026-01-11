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

## 项目结构

```
backend/
├── app/                          # 应用主目录
│   ├── api/v1/                  # API路由层
│   ├── core/                    # 核心配置（config、security、deps）
│   ├── models/                  # SQLAlchemy数据模型
│   │   ├── user.py              # 用户模型
│   │   ├── session.py           # 会话模型 (NEW)
│   │   ├── chat_history.py      # 历史记录模型 (NEW)
│   │   └── ...
│   ├── schemas/                 # Pydantic数据验证模式
│   ├── services/                # 业务逻辑层
│   │   ├── session_service.py   # 会话服务 (NEW)
│   │   ├── context_manager.py   # 上下文管理器 (NEW)
│   │   ├── rag_service.py       # RAG服务
│   │   └── ...
│   ├── tasks/                   # Celery异步任务
│   ├── utils/                   # 工具函数
│   │   ├── redis_client.py      # Redis客户端 (NEW)
│   │   └── ...
│   ├── db/                      # 数据库会话管理
│   └── main.py                  # FastAPI应用入口
├── data/                        # 数据目录
│   └── files/                   # 上传文件存储
├── models/Qwen/                 # Embedding模型
├── sql/                         # 数据库DDL脚本
├── docker-compose.yaml          # Docker服务编排
├── pyproject.toml               # 项目配置和依赖（uv/pip）
├── requirements.txt             # Python依赖（兼容pip）
├── uv.lock                      # 依赖锁定文件（uv生成）
├── .env.example                 # 环境配置模板
└── README.md                    # 项目说明
```

## 快速开始

### 1. 环境准备

**系统要求**：
- Python 3.10 - 3.12
- Docker 和 Docker Compose
- Git
- **uv** （推荐）或 pip

**克隆项目**：
```bash
cd backend
```

### 2. 安装 uv 包管理工具

uv 是一个极快的 Python 包管理工具，由 Rust 编写，可以替代 pip、pip-tools 和 virtualenv。

**Windows 安装**：

```powershell
# 使用 PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或使用 pip 安装
pip install uv

# 或使用 pipx 安装
pipx install uv
```

**Linux/macOS 安装**：
```bash
# 使用官方安装脚本
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip 安装
pip install uv

# 或使用 Homebrew (macOS)
brew install uv
```

**验证安装**：
```bash
uv --version
```

### 3. 创建虚拟环境并安装依赖

**方式一：使用 uv （推荐）**

```bash
# 创建虚拟环境（使用 Python 3.10）
uv venv --python 3.10

# 激活虚拟环境
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (CMD)
.venv\Scripts\activate.bat


# Windows (Git Bash)
source .venv/Scripts/activate
# Linux/macOS
source .venv/bin/activate

# 安装依赖（从 pyproject.toml）
uv pip install -e .

# 或者安装依赖（从 requirements.txt）
uv pip install -r requirements.txt

# 安装开发依赖（可选）
uv pip install -e ".[dev]"
```

**方式二：使用 uv sync （最简单，推荐使用）**

```bash
# uv 会自动创建虚拟环境并安装依赖     使用管理员运行
uv sync

# 激活虚拟环境
# Windows
.venv\Scripts\activate


# Linux/macOS
source .venv/bin/activate
```

**方式三：使用传统 pip**

如果不使用 uv，也可以使用传统的 pip：

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

### 4. 启动依赖服务

使用 Docker Compose 启动 MySQL、Elasticsearch、Milvus、Redis 等服务：

```bash
docker-compose up -d
```

等待服务启动完成（约1-2分钟），可以通过以下命令检查服务状态：

```bash
docker-compose ps
```

### 5. 配置环境变量

复制环境配置模板并修改：

```bash
cp .env.example .env
```

编辑 `.env` 文件，修改以下关键配置：
- `JWT_SECRET_KEY`: 修改为随机字符串（至少32字符）
- `AES_ENCRYPTION_KEY`: 修改为32字节随机字符串
- 其他配置根据实际情况调整

### 6. 初始化数据库和对应的插件

执行数据库 DDL 脚本：

```bash
# 方式1：使用MySQL客户端
mysql -h localhost -u root -proot < sql/ddl.txt

# 方式2：使用docker exec
docker exec -i rag-mysql8 mysql -u root -proot < sql/ddl.txt
```

安装ik分词器

```bash
# 在 ES 容器中安装 IK 分词器（版本需与 ES 版本匹配，这里是 7.17.10）
docker exec -it rag-es7 elasticsearch-plugin install https://github.com/infinilabs/analysis-ik/releases/download/v7.17.10/elasticsearch-analysis-ik-7.17.10.zip、

# 网络有问题就手动下载（https://release.infinilabs.com/analysis-ik/stable/）   手动下载之后记得copy到容器中
docker cp xxxx(your_root_path)\elasticsearch-analysis-ik-7.17.10.zip rag-es7:/tmp/

# 进入容器内部
docker exec -it rag-es7 /bin/bash

# 在容器内部执行如下的命令
# 创建 ik 目录
mkdir -p /usr/share/elasticsearch/plugins/ik

# 解压到 ik 目录
unzip /tmp/elasticsearch-analysis-ik-7.17.10.zip -d /usr/share/elasticsearch/plugins/ik

# （可选）删除压缩包
rm /tmp/elasticsearch-analysis-ik-7.17.10.zip   

# 重启 ES 容器使插件生效
docker restart rag-es7
```





### 7. 启动应用

**启动 FastAPI 服务**：

```bash
# 确保已激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 开发模式（支持热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**使用 uv run 直接运行**（无需手动激活环境）：

```bash
# uv run 会自动使用项目的虚拟环境
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**启动 Celery Worker**（新终端）：

```bash
# 方式一：激活环境后运行
celery -A app.tasks.celery_app worker --loglevel=info -Q document_processing

# 方式二：使用 uv run
uv run celery -A app.tasks.celery_app worker --loglevel=info
```

### 8. 访问 API 文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 9. 测试接口

访问健康检查接口：

```bash
curl http://localhost:8000/api/v1/health
```

---

## uv 常用命令参考

### 环境管理

```bash
# 创建虚拟环境
uv venv

# 指定 Python 版本创建虚拟环境
uv venv --python 3.11

# 同步依赖（自动创建环境并安装依赖）
uv sync

# 同步包含开发依赖
uv sync --all-extras
```

### 包管理

```bash
# 安装包
uv pip install <package>

# 卸载包
uv pip uninstall <package>

# 升级包
uv pip install --upgrade <package>

# 从 requirements.txt 安装
uv pip install -r requirements.txt

# 从 pyproject.toml 安装（可编辑模式）
uv pip install -e .

# 查看已安装的包
uv pip list

# 查看包信息
uv pip show <package>
```

### 运行命令

```bash
# 在项目环境中运行命令
uv run <command>

# 示例
uv run python script.py
uv run pytest
uv run uvicorn app.main:app --reload
```

### 锁定文件

```bash
# 生成锁定文件
uv lock

# 查看锁定文件
cat uv.lock
```

## 核心功能

### 用户认证与管理
- ✅ 用户注册、登录（JWT认证）
- ✅ 用户信息管理
- ✅ 角色权限控制（Admin/User）

### 知识库管理
- ✅ 创建/查询/修改/删除知识库
- ✅ 配置 Embedding 模型
- ✅ 文档切片参数配置

### 文档管理
- ✅ 上传文档（PDF/DOCX/MD/HTML/TXT）
- ✅ 异步文档解析与向量化
- ✅ 文档状态跟踪
- ✅ 文档删除与重新处理

### 机器人配置
- ✅ 创建/配置问答机器人
- ✅ 关联知识库
- ✅ 配置检索参数（top_k、相似度阈值）
- ✅ 配置 Prompt 模板

### RAG 问答服务
- ✅ 混合检索（向量检索 + BM25关键词检索）
- ✅ RRF 融合排序
- ✅ 多轮对话上下文支持 (NEW)
- ✅ 引用来源追踪

### 会话管理 (NEW)
- ✅ 用户会话创建/查询/更新/删除
- ✅ 会话历史记录持久化
- ✅ 会话置顶/归档功能
- ✅ 用户反馈系统

### 上下文管理 (NEW)
- ✅ Redis 热数据缓存
- ✅ 最多10轮对话上下文限制
- ✅ 上下文自动过期清理
- ✅ 会话锁防止并发冲突

### LLM 模型管理
- ✅ 配置多种 LLM 模型
- ✅ API Key 加密存储
- ✅ 模型类型区分（Chat/Embedding/Rerank）

## 开发指南

### 代码规范

- 遵循 PEP 8 代码风格
- 使用类型注解（Type Hints）
- 函数和类添加文档字符串
- 使用 Black 格式化代码

### 分层架构

```
API Layer (api/v1/)
    ↓
Service Layer (services/)
    ↓
Data Access Layer (models/ + db/)
    ↓
Database (MySQL/ES/Milvus/Redis)
```

### API 接口概览

#### 对话问答 API

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/v1/chat/ask` | POST | 对话问答（支持多轮） |
| `/api/v1/chat/sessions` | POST | 创建新会话 |
| `/api/v1/chat/sessions` | GET | 获取会话列表 |
| `/api/v1/chat/sessions/{id}` | GET | 获取会话详情 |
| `/api/v1/chat/sessions/{id}` | PUT | 更新会话 |
| `/api/v1/chat/sessions/{id}` | DELETE | 删除会话 |
| `/api/v1/chat/history/{id}` | GET | 获取会话历史 |
| `/api/v1/chat/feedback` | POST | 提交消息反馈 |
| `/api/v1/chat/test` | POST | 测试知识库检索 |

#### 其他 API

| 模块 | 前缀 | 描述 |
|------|------|------|
| 认证 | `/api/v1/auth` | 登录/注册 |
| 用户 | `/api/v1/users` | 用户管理 |
| 知识库 | `/api/v1/knowledge` | 知识库CRUD |
| 文档 | `/api/v1/documents` | 文档上传/管理 |
| 机器人 | `/api/v1/robots` | 机器人CRUD |
| LLM | `/api/v1/llms` | 模型配置 |
| API Key | `/api/v1/apikeys` | 密钥管理 |

### 添加新接口

1. 在 `app/schemas/` 中定义请求和响应模型
2. 在 `app/services/` 中实现业务逻辑
3. 在 `app/api/v1/` 中定义路由和接口
4. 在 `app/main.py` 中注册路由

### 运行测试

```bash
# 使用 uv run 运行测试
uv run pytest tests/

# 或者激活环境后运行
pytest tests/

# 运行特定测试文件
uv run pytest tests/test_auth.py

# 生成覆盖率报告
uv run pytest --cov=app tests/
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

## 常见问题

### 1. Elasticsearch 连接失败

确保 Elasticsearch 服务已启动并安装 IK 分词器：

```bash
# 检查ES状态
curl http://localhost:9200

# 安装IK分词器
docker exec -it rag-es7 elasticsearch-plugin install https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v7.17.21/elasticsearch-analysis-ik-7.17.21.zip
docker restart rag-es7
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
# 检查Redis状态
docker-compose logs redis

# 测试连接
redis-cli ping
```

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
| `rag_session` | 用户会话表 (NEW) |
| `rag_chat_history` | 历史问答记录表 (NEW) |

## Redis 数据结构

| Key模式 | 类型 | 描述 | TTL |
|---------|------|------|-----|
| `rag:session:{id}:context` | Hash | 会话上下文元数据 | 2小时 |
| `rag:session:{id}:messages` | List | 对话历史消息 | 2小时 |
| `rag:user:{id}:active_sessions` | Sorted Set | 用户活跃会话 | 24小时 |
| `rag:session:{id}:lock` | String | 会话锁 | 30秒 |

## 许可证

MIT License

## 参与贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目文档：查看 `.qoder/quests/` 目录中的设计文档
- 技术支持：提交 GitHub Issue

---

**更新日志**

- 2026-01-04: 添加会话管理和上下文管理功能，支持多轮对话
- 2026-01-04: 切换包管理工具为 uv，添加 pyproject.toml 配置
