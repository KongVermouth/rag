# 企业级 RAG 知识问答系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Next.js: 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)

这是一个基于检索增强生成（Retrieval-Augmented Generation, RAG）技术的全栈智能知识问答系统。系统支持多格式文档上传、自动化解析、语义切片、向量化存储及混合搜索，旨在为企业提供高效、精准的本地知识问答能力。

---

## 🚀 项目特性

- **全异步后端**: 基于 FastAPI 实现的高性能异步 API，确保高并发处理能力。
- **现代化前端**: 采用 Next.js 14 (App Router) 构建，响应式设计，极致的用户体验。
- **去 LangChain 化**: 核心逻辑自研实现，降低复杂度，提升系统可控性与性能。
- **混合检索策略**: 结合 Milvus 向量检索与 Elasticsearch 全文检索（IK 分词），大幅提升召回精度。
- **文档全生命周期管理**: 支持 PDF、Word、TXT、Markdown、HTML 等多种格式的自动化处理。
- **微服务 Worker 架构**: 文档解析、切片、向量化均通过 Kafka 消息队列异步解耦处理。
- **SiliconFlow 深度集成**: 针对大模型 Embedding 接口提供自动分批、指数退火重试及详细错误诊断。

---

## 🛠️ 技术栈

### 后端 (Backend)
- **框架**: FastAPI
- **异步驱动**: SQLAlchemy (Async), aiomysql, aiokafka, redis-py, elasticsearch-py
- **向量检索**: Milvus 2.4.x
- **全文检索**: Elasticsearch 7.17.x (含 IK 分词器)
- **消息队列**: Apache Kafka 3.6.x
- **Embedding 模型**: 本地部署 Qwen3-Embedding-0.6B
- **日志管理**: Loguru

### 前端 (Frontend)
- **框架**: Next.js 14 (App Router)
- **状态管理**: Zustand
- **样式**: Tailwind CSS
- **HTTP 客户端**: Axios
- **可视化**: Recharts

### 基础设施 (Infrastructure)
- **容器化**: Docker & Docker Compose
- **存储**: MySQL 8.0, Redis 7.2, MinIO

---

## 📂 目录结构

```text
rag/
├── backend/                # 后端服务
│   ├── app/                # 核心逻辑
│   ├── config/             # 模型与业务配置
│   ├── data/               # 本地存储 (原始文件、清洗结果)
│   ├── models/             # 本地 Embedding 模型权重
│   ├── scripts/            # 数据库维护与 ES 插件脚本
│   ├── sql/                # 数据库初始化脚本
│   ├── tests/              # 单元测试与压力测试
│   └── main.py             # 入口文件
├── front/                  # 前端应用
│   ├── src/                # 源代码
│   └── cypress/            # E2E 测试
├── docker-compose.yaml      # 基础架构容器配置
└── README.md                # 项目总文档
```

---

## 🏁 快速开始

### 1. 环境准备
确保已安装以下工具：
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/)
- [Python 3.10+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)

### 2. 启动基础架构
在根目录下启动所有中间件容器：
```bash
docker-compose up -d
```
等待服务启动后，务必安装 Elasticsearch IK 分词器：
```bash
# 在 ES 容器中安装插件
docker exec -it rag-es7 elasticsearch-plugin install https://github.com/infinilabs/analysis-ik/releases/download/v7.17.10/elasticsearch-analysis-ik-7.17.10.zip
# 重启 ES
docker restart rag-es7
```

### 3. 配置后端
```bash
cd backend
# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 下载 Embedding 模型
python src/download_models.py

# 初始化配置
cp .env.example .env
# 根据实际环境修改 .env 中的数据库及密钥配置

# 启动后端服务
python main.py

# 启动异步 Workers (需独立终端)
python -m app.workers.parser
python -m app.workers.splitter
python -m app.workers.vectorizer
```

### 4. 配置前端
```bash
cd front
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```
访问 `http://localhost:3000` 即可开始体验。

---

## 🔑 环境变量说明

| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `DB_PASSWORD` | MySQL 密码 | `rag_jin` |
| `JWT_SECRET_KEY` | JWT 签发密钥 | 请务必修改 |
| `AES_ENCRYPTION_KEY` | API Key 加密密钥 (32位) | 请务必修改 |
| `ES_HOST` | Elasticsearch 地址 | `http://localhost:9200` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka 地址 | `localhost:9094` |
| `NEXT_PUBLIC_API_URL` | 前端调用的后端地址 | `http://localhost:8000` |

---

## 📖 API 接口文档

后端服务启动后，可通过以下地址查看详细的 Swagger UI 文档：
- **API 文档**: `http://localhost:8000/docs`
- **健康检查**: `http://localhost:8000/health`

---

## 🧪 测试与质量

### 后端
```bash
cd backend
# 运行单元测试
pytest tests/
# 运行压力测试
python tests/stress_test_upload.py
# 代码检查
ruff check .
```

### 前端
```bash
cd front
# 运行 Lint
npm run lint
# 运行 E2E 测试
npm run cypress:open
```

---

## 🤝 贡献指南

1. Fork 本项目。
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)。
4. 推送到分支 (`git push origin feature/AmazingFeature`)。
5. 提交 Pull Request。

---

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

---

## 📝 更新日志

详见 [backend/CHANGELOG.md](backend/CHANGELOG.md)。
