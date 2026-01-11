# RAG 前端应用

基于 Next.js 14 构建的 RAG (检索增强生成) 系统前端应用程序。

## 技术栈

- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **状态管理**: Zustand
- **样式**: Tailwind CSS
- **HTTP 客户端**: Axios
- **图标**: Lucide React
- **通知**: React Hot Toast
- **Markdown**: React Markdown

## 项目结构

```
front/
├── src/
│   ├── api/              # API 服务层
│   │   ├── auth.ts       # 认证与用户 API
│   │   ├── knowledge.ts  # 知识库 API
│   │   ├── document.ts   # 文档 API
│   │   ├── robot.ts      # 机器人 API
│   │   ├── llm.ts        # LLM 模型 API
│   │   ├── apikey.ts     # API 密钥 API
│   │   └── chat.ts       # 聊天与会话 API
│   ├── app/              # Next.js App Router 页面
│   │   ├── auth/         # 认证页面（登录、注册）
│   │   ├── chat/         # 聊天界面
│   │   ├── knowledge/    # 知识库管理
│   │   ├── robots/       # 机器人配置
│   │   ├── admin/        # 管理员面板
│   │   ├── layout.tsx    # 根布局
│   │   └── page.tsx      # 首页
│   ├── components/       # React 组件
│   │   ├── layout/       # 布局组件
│   │   └── ui/           # UI 组件库
│   ├── lib/              # 工具库
│   │   ├── api-client.ts # Axios 客户端配置
│   │   └── utils.ts      # 工具函数
│   ├── stores/           # Zustand 状态管理
│   │   ├── auth-store.ts # 认证状态
│   │   ├── theme-store.ts# 主题状态
│   │   └── chat-store.ts # 聊天状态
│   └── types/            # TypeScript 类型定义
│       └── index.ts      # 所有类型定义
├── public/               # 静态资源
├── .env.local            # 环境变量
├── next.config.js        # Next.js 配置
├── tailwind.config.ts    # Tailwind 配置
├── tsconfig.json         # TypeScript 配置
└── package.json          # 依赖配置
```

## 功能模块

### 1. 用户认证
- 用户注册
- 用户登录
- JWT Token 管理
- 自动登录状态保持

### 2. 知识库管理
- 创建知识库
- 编辑知识库信息
- 删除知识库
- 查看知识库统计

### 3. 文档管理
- 上传文档（支持 PDF、Word、TXT、MD）
- 查看文档处理状态
- 删除文档
- 重新处理文档

### 4. 机器人配置
- 创建机器人
- 配置 LLM 模型
- 关联知识库
- 设置系统提示词
- 调整参数（temperature, top_k, max_tokens）

### 5. 聊天界面
- 实时对话
- 多轮对话支持
- 引用来源显示
- 会话历史管理
- 消息反馈

### 6. 管理员面板
- 用户管理
- LLM 模型配置
- API 密钥管理

## 环境配置

创建 `.env.local` 文件：

```env
# API 基础 URL
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1

# 应用名称
NEXT_PUBLIC_APP_NAME=RAG Assistant
```

## 安装与运行

### 开发环境

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 访问 http://localhost:3000
```

### 生产构建

```bash
# 构建生产版本
npm run build

# 启动生产服务器
npm start
```

### Docker 部署

```bash
# 构建镜像
docker build -t rag-frontend .

# 运行容器
docker run -p 3000:3000 -e NEXT_PUBLIC_API_BASE_URL=http://your-api-server:8000/api/v1 rag-frontend
```

## API 集成说明

### 认证流程

1. 用户登录后获取 JWT Token
2. Token 存储在 localStorage
3. Axios 拦截器自动添加 Authorization 头
4. Token 过期自动跳转登录页

### API 端点对应

| 前端功能 | 后端 API |
|---------|---------|
| 登录 | POST /api/v1/auth/login |
| 注册 | POST /api/v1/auth/register |
| 知识库列表 | GET /api/v1/knowledge |
| 创建知识库 | POST /api/v1/knowledge |
| 上传文档 | POST /api/v1/documents/upload |
| 机器人列表 | GET /api/v1/robots |
| 发送消息 | POST /api/v1/chat |
| 流式聊天 | POST /api/v1/chat/stream |

### 错误处理

- 401: 未认证，跳转登录页
- 403: 无权限，显示错误提示
- 500: 服务器错误，显示错误提示

## 开发指南

### 添加新页面

1. 在 `src/app/` 下创建目录和 `page.tsx`
2. 使用 `MainLayout` 组件包裹页面内容
3. 在 Header 组件中添加导航链接

### 添加新 API

1. 在 `src/api/` 下创建或修改 API 文件
2. 在 `src/types/index.ts` 添加类型定义
3. 使用 `apiClient` 发送请求

### 添加新组件

1. 在 `src/components/ui/` 下创建组件
2. 使用 TypeScript 定义 Props 接口
3. 支持 className 属性便于样式定制

## 主题切换

支持三种主题模式：
- **浅色模式**: 明亮的背景色
- **深色模式**: 暗黑背景色
- **跟随系统**: 自动匹配系统设置

切换方式：点击页面头部的主题切换按钮

## 响应式设计

- **桌面端**: 完整功能展示
- **平板端**: 适配中等屏幕
- **移动端**: 简化布局，隐藏侧边栏

## 浏览器支持

- Chrome (推荐)
- Firefox
- Safari
- Edge

## 常见问题

### Q: 登录后跳转不正确？
A: 检查 `.env.local` 中的 API 地址配置是否正确。

### Q: 文件上传失败？
A: 确保后端服务已启动，且文件大小不超过限制。

### Q: 聊天无响应？
A: 检查机器人是否已关联知识库，且 LLM 模型配置正确。

## 许可证

MIT License
