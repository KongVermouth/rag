# LLM 厂商兼容性重构报告

## 1. 架构设计
采用了 **适配器模式 (Adapter Pattern)** 和 **工厂模式 (Factory Pattern)** 对 LLM 调用层进行了重构。

- **抽象基类 (`BaseLLMProvider`)**: 定义了统一的 `chat`, `chat_stream`, `embed`, `rerank` 接口。
- **标准化数据模型**: 使用 Pydantic 定义了统一的 `LLMRequest`, `LLMResponse`, `LLMStreamChunk`。
- **厂商适配器**:
  - `OpenAIProvider`: 支持 OpenAI, DeepSeek, SiliconFlow, MiniMax, 智谱, 阿里等兼容接口。
  - `AnthropicProvider`: 支持 Claude 系列模型。
  - `GoogleProvider`: 支持 Gemini 系列模型（含向量化）。
  - `BaiduProvider`: 支持文心一言系列模型（含向量化）。
- **动态工厂 (`LLMFactory`)**: 根据配置自动路由到对应的适配器。

## 2. 厂商兼容性矩阵

| 厂商 | API 格式 | 鉴权方式 | 流式输出 | 向量化 | 重排序 | 备注 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **OpenAI** | OpenAI V1 | Bearer Token | 支持 (SSE) | 支持 | 不支持 | 标准参考 |
| **DeepSeek** | OpenAI 兼容 | Bearer Token | 支持 (SSE) | 支持 | 不支持 | 支持推理内容显示 |
| **Anthropic** | Anthropic V1 | Custom Header | 支持 (SSE) | 不支持 | 不支持 | - |
| **Google** | Gemini V1 | API Key (Query) | 支持 (SSE) | 支持 | 不支持 | - |
| **百度** | RPC / Custom | OAuth 2.0 | 支持 (SSE) | 支持 | 不支持 | 自动处理 Token 刷新 |
| **MiniMax** | OpenAI 兼容+ | Bearer Token | 支持 (SSE) | 支持 | 不支持 | 已适配 `tokens_to_generate` |

## 3. 接入指南

### 添加新厂商
1. 在 `app/core/llm/providers/` 下创建新的适配器类，继承 `BaseLLMProvider`。
2. 实现 `chat` 和 `chat_stream` 等必要方法。
3. 在 `app/core/llm/factory.py` 的 `_providers` 字典中注册新厂商。

### 调用示例
```python
from app.core.llm.factory import LLMFactory
from app.core.llm.base import LLMRequest, LLMMessage

# 获取适配器
provider = LLMFactory.get_provider(
    provider_name="openai",
    api_key="sk-...",
    base_url="https://api.openai.com/v1"
)

# 构建请求
request = LLMRequest(
    messages=[LLMMessage(role="user", content="你好")],
    model="gpt-4"
)

# 发起调用
response = await provider.chat(request)
print(response.content)
```

## 4. 优化点
- **异常处理**: 统一了各厂商的错误捕获逻辑，屏蔽了原始 HTTP 报错。
- **流式解析**: 自动处理不同厂商 SSE 推送格式的微小差异（如 `data:` 后是否有空格）。
- **故障转移**: 提供了 `FailoverProvider` 支持主备模型自动切换。
