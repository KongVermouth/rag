# RAG 知识问答系统

基于检索增强生成（Retrieval-Augmented Generation）技术的智能知识问答系统，支持文档管理、向量化存储、智能问答等功能。

## 目录

- [项目简介](#项目简介)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [安装部署](#安装部署)
- [项目结构](#项目结构)
- [API文档](#api文档)

---

## 项目简介

本系统是一个企业级 RAG 知识问答平台，主要功能包括：

- **用户认证**: 用户注册、登录、JWT Token 认证
- **知识库管理**: 文档上传、解析、切片、向量化存储
- **机器人管理**: 创建和管理 AI 问答机器人
- **智能问答**: 基于向量检索的上下文感知问答
- **会话管理**: 多轮对话上下文管理

---

## 技术栈

### 后端技术

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架 |
| **SQLAlchemy** | ORM 数据库访问 |
| **MySQL 8.0** | 关系型数据库 |
| **Redis** | 缓存、会话存储 |
| **Milvus** | 向量数据库 |
| **Elasticsearch** | 全文检索 |
| **Celery** | 异步任务队列 |
| **JWT** | 认证授权 |

### 前端技术

| 技术 | 用途 |
|------|------|
| **Next.js 14** | React 框架 |
| **React 18** | UI 库 |
| **Zustand** | 状态管理 |
| **Tailwind CSS** | 样式框架 |
| **Axios** | HTTP 客户端 |
| **Recharts** | 图表组件 |

### 基础设施

| 技术 | 用途 |
|------|------|
| **Docker** | 容器化部署 |
| **MinIO** | 对象存储 |
| **Attu** | Milvus Web 管理 |

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户浏览器                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端服务 (Next.js)                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  用户管理   │  │  知识库管理  │  │  机器人管理  │  │  智能问答   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              后端服务 (FastAPI)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                           API Gateway                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  认证模块   │  │  用户模块   │  │  知识模块   │  │  问答模块   │        │
│  │  (JWT)      │  │  (CRUD)     │  │  (RAG)      │  │  (Chat)     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                        │
│  │  文档模块   │  │  会话模块   │  │  API Key    │                        │
│  │  (Upload)   │  │  (Session)  │  │  (Manage)   │                        │
│  └─────────────┘  └─────────────┘  └─────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────┐
│   MySQL 8.0      │    │     Redis 缓存           │    │   Milvus 向量    │
│  (用户/会话/配置) │    │  (会话/上下文缓存)        │    │   (文档向量化)   │
└──────────────────┘    └──────────────────────────┘    └──────────────────┘
          │                           │                           │
          ▼                           ▼                           ▼
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────┐
│ Elasticsearch    │    │    MinIO 对象存储        │    │   Celery 异步    │
│  (全文检索)      │    │   (原始文件存储)         │    │   (文档处理)     │
└──────────────────┘    └──────────────────────────┘    └──────────────────┘
```

### 后端架构逻辑图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Backend Application                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Presentation Layer                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │   FastAPI    │  │    Swagger   │  │   CORS       │              │    │
│  │  │   Endpoints  │  │    Docs      │  │   Middleware │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Application Layer                              │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │   Services   │  │   Schemas    │  │   Tasks      │              │    │
│  │  │   (业务逻辑)  │  │   (数据验证)  │  │   (Celery)   │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  │       │                  │                  │                        │    │
│  │       ▼                  ▼                  ▼                        │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │              Service Layer - 核心服务模块                      │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │    │
│  │  │  │AuthService│ │UserService│ │LLMService│ │APIKeyService│    │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │    │
│  │  │  │DocService│ │Knowledge │ │RAGService│ │SessionSvc │        │   │    │
│  │  │  │          │ │Service   │ │          │ │          │        │   │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                          Domain Layer                                 │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                      Models (SQLAlchemy)                      │   │    │
│  │  │  User │ LLM │ APIKey │ Document │ Knowledge │ Session │ ChatHistory │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│                                      ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                       Infrastructure Layer                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │  Database    │  │  Vector DB   │  │  Search      │              │    │
│  │  │  (MySQL)     │  │  (Milvus)    │  │  (ES)        │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │    │
│  │  │  Cache       │  │  Storage     │  │  Embedding   │              │    │
│  │  │  (Redis)     │  │  (MinIO)     │  │  (Transform) │              │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 安装部署

### 前置条件

| 工具 | 版本要求 |
|------|----------|
| Python | 3.10+ |
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Git | 2.0+ |

### 步骤 1：创建 Python 虚拟环境

```bash
# 进入后端目录
cd backend

# 创建虚拟环境 (使用 venv)
python -m venv .venv

# 有miniconda或者conda   使用conda即可
conda create -n rag python==3.10
conda activate rag

# 激活虚拟环境
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 步骤 2：安装 Python 依赖包

```bash
# 使用 pip 安装
pip install -r requirements.txt

# 或使用 uv (推荐，速度更快)
uv pip install -r requirements.txt
```

**注意**: 如需 GPU 加速支持，请额外安装 PyTorch CUDA 版本：

```bash
pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 \
    --index-url https://download.pytorch.org/whl/cu124
```

### 步骤 3：下载 Embedding 模型

```bash
# 使用提供的脚本下载模型
cd backend/src

# 默认下载 Qwen3-Embedding-0.6B 模型到 ../models 目录
python download_models.py

# 模型将保存在 backend/models/Qwen/Qwen3-Embedding-0___6B/
```

### 步骤 4：启动 Docker 容器

```bash
# 在 backend 目录下执行
docker-compose up -d

# 启动后检查容器状态
docker-compose ps
```

**启动的容器列表**:
| 容器名 | 端口 | 服务 |
|--------|------|------|
| rag-mysql8 | 3306 | MySQL 8.0 |
| rag-es7 | 9200/9300 | Elasticsearch 7.17 |
| rag-kibana | 5601 | Kibana |
| rag-etcd | 2379 | etcd |
| rag-minio | 9000/9001 | MinIO |
| rag-milvus | 19530/9091 | Milvus |
| rag-attu | 8001 | Attu (Milvus UI) |
| rag-redis | 6379 | Redis |

### 步骤 5：执行 DDL 语句

```bash
# 等待 MySQL 容器完全启动后，执行建表脚本
docker exec -i rag-mysql8 mysql -uroot -proot rag_system < sql/init_schema.sql
```

或者通过数据库管理工具（如 MySQL Workbench、Navicat）连接后执行 `sql/init_schema.sql` 文件中的 SQL 语句。

### 步骤6：安装ik分词器

```bash
# 在 ES 容器中安装 IK 分词器
docker exec -it rag-es7 elasticsearch-plugin install https://github.com/infinilabs/analysis-ik/releases/download/v7.17.10/elasticsearch-analysis-ik-7.17.10.zip

# 重启 ES 容器使插件生效
docker restart rag-es7
```

### 步骤 7：配置环境变量

```bash
# 复制环境变量模板
cd backend
cp .env.example .env

# 编辑 .env 文件，修改配置
# 关键配置项：
# - JWT_SECRET_KEY: JWT 密钥 (至少32字符)
# - AES_ENCRYPTION_KEY: API Key 加密密钥 (32字符)
# - DB_PASSWORD: 数据库密码
```

### 步骤 8：启动后端服务

```bash
# 开发模式启动 (自动重载)
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用
python main.py
```

后端服务启动后：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 步骤 9：启动前端服务

```bash
# 进入前端目录
cd front

# 安装依赖 (首次运行)
npm install

# 启动开发服务器
npm run dev
```

前端服务启动后：
- 访问地址: http://localhost:3000

---

## 项目结构

```
rag/
├── backend/                      # 后端项目
│   ├── app/                      # FastAPI 应用
│   │   ├── api/v1/               # API 路由层
│   │   │   ├── auth.py           # 认证接口
│   │   │   ├── users.py          # 用户接口
│   │   │   ├── documents.py      # 文档接口
│   │   │   ├── knowledge.py      # 知识库接口
│   │   │   ├── robots.py         # 机器人接口
│   │   │   ├── chat.py           # 问答接口
│   │   │   ├── llms.py           # LLM 配置接口
│   │   │   └── apikeys.py        # API Key 接口
│   │   ├── core/                 # 核心配置
│   │   │   ├── config.py         # 配置类
│   │   │   ├── security.py       # 安全工具 (JWT, 加密)
│   │   │   └── deps.py           # 依赖注入
│   │   ├── db/                   # 数据库层
│   │   │   ├── session.py        # 数据库会话
│   │   │   └── base.py           # 基类
│   │   ├── models/               # 数据模型
│   │   │   ├── user.py           # 用户模型
│   │   │   ├── document.py       # 文档模型
│   │   │   ├── knowledge.py      # 知识库模型
│   │   │   ├── robot.py          # 机器人模型
│   │   │   ├── session.py        # 会话模型
│   │   │   └── chat_history.py   # 聊天记录模型
│   │   ├── schemas/              # Pydantic 模式
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── auth_service.py   # 认证服务
│   │   │   ├── rag_service.py    # RAG 问答服务
│   │   │   └── ...
│   │   ├── tasks/                # Celery 异步任务
│   │   ├── utils/                # 工具类
│   │   │   ├── embedding.py      # 向量化工具
│   │   │   ├── file_parser.py    # 文件解析
│   │   │   ├── text_splitter.py  # 文本切分
│   │   │   ├── milvus_client.py  # Milvus 客户端
│   │   │   └── es_client.py      # ES 客户端
│   │   └── main.py               # 应用入口
│   ├── data/                     # 数据目录
│   │   ├── raw_data/             # 原始文件
│   │   ├── cleaned_md/           # 清洗后的 Markdown
│   │   └── cleaned_txt/          # 清洗后的 Text
│   ├── models/                   # 本地模型存储
│   │   └── Qwen/                 # Qwen 模型
│   ├── sql/                      # SQL 脚本
│   │   └── init_schema.sql       # 数据库初始化
│   ├── src/                      # 工具脚本
│   │   ├── download_models.py    # 模型下载脚本
│   │   └── embedding_demo.py     # 向量化示例
│   ├── docker-compose.yaml       # Docker Compose 配置
│   ├── requirements.txt          # Python 依赖
│   ├── .env.example              # 环境变量模板
│   └── README.md                 # 后端文档
│
├── front/                        # 前端项目 (Next.js)
│   ├── src/                      # 源代码
│   │   ├── app/                  # Next.js App Router
│   │   ├── components/           # React 组件
│   │   ├── store/                # Zustand 状态管理
│   │   ├── services/             # API 服务
│   │   └── utils/                # 工具函数
│   ├── public/                   # 静态资源
│   ├── package.json              # npm 依赖
│   ├── tailwind.config.ts        # Tailwind 配置
│   └── Dockerfile
│
└── README.md                     # 项目主文档
```

---

## API 文档

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/auth/me` | 获取当前用户 |
| POST | `/api/v1/auth/refresh` | 刷新 Token |

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat/{robot_id}` | 机器人问答 |
| POST | `/api/v1/documents/upload` | 上传文档 |
| POST | `/api/v1/knowledge/{id}/index` | 索引知识库 |
| GET | `/api/v1/robots` | 获取机器人列表 |

详细 API 文档请访问: http://localhost:8000/docs

---

## 默认账号

首次启动时，系统会自动创建默认管理员账号：

| 字段 | 值 |
|------|------|
| 邮箱 | admin@example.com |
| 密码 | Admin@123 |

**注意**: 首次登录后请及时修改默认密码。

---

## 常见问题

### 1. Docker 容器启动失败

```bash
# 检查容器日志
docker-compose logs

# 查看具体错误
docker-compose logs mysql8
```

### 2. 模型下载失败

```bash
# 设置 ModelScope Token (可选)
export MODELSCOPE_SDK_TOKEN="your_token"

# 重新下载
python src/download_models.py
```

### 3. Milvus 连接失败

确保 MinIO 和 etcd 容器正常运行后再启动 Milvus：

```bash
# 按依赖顺序启动
docker-compose up -d etcd minio milvus-standalone
```

---

## License

MIT License
