import apiClient from '@/lib/api-client';
import type {
  ChatRequest,
  ChatResponse,
  KnowledgeTestRequest,
  KnowledgeTestResponse,
  Session,
  SessionCreate,
  SessionUpdate,
  SessionDetail,
  SessionListResponse,
  FeedbackRequest,
  MessageResponse,
  ChatStreamChunk
} from '@/types';

/**
 * 聊天对话API
 */
export const chatApi = {
  // 发送对话消息
  ask: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>('/chat/ask', data);
    return response.data;
  },

  // 流式发送对话消息 - 新的 event/data 格式
  askStream: async (
    data: ChatRequest,
    onChunk: (chunk: ChatStreamChunk) => void,
    onError?: (error: Error) => void,
    signal?: AbortSignal
  ): Promise<void> => {
    const token = localStorage.getItem('token');
    // 获取 API 地址，Next.js 使用 NEXT_PUBLIC_API_URL
    const baseUrl = typeof process !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      : 'http://localhost:8000';
    // 确保 baseUrl 结尾没有斜杠
    const cleanBaseUrl = baseUrl.replace(/\/$/, '');

    // 构造完整的 API URL
    const apiUrl = `${cleanBaseUrl}/api/v1/chat/ask/stream`;

    // 创建新的 AbortController 以支持外部取消
    const controller = new AbortController();
    const abortSignal = signal || controller.signal;

    // 监听外部 AbortSignal
    const abortHandler = () => controller.abort();
    signal?.addEventListener('abort', abortHandler);

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify(data),
        signal: controller.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';

      while (true) {
        // 检查是否已取消
        if (abortSignal.aborted) {
          throw new Error('Request aborted');
        }

        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按行解析 SSE 格式
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            // 提取事件类型
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            // 提取数据
            try {
              const dataStr = line.slice(6).trim();
              if (!dataStr) continue;

              const chunk = JSON.parse(dataStr) as ChatStreamChunk;
              // 添加事件类型信息
              (chunk as any)._eventType = currentEvent;
              onChunk(chunk);
            } catch (e) {
              // 跳过解析错误
            }
          }
        }
      }
    } catch (error) {
      // 清理监听器
      signal?.removeEventListener('abort', abortHandler);

      if (abortSignal.aborted) {
        const abortError = new Error('Request aborted');
        abortError.name = 'AbortError';
        if (onError) {
          onError(abortError);
        }
        throw abortError;
      }
      if (onError && error instanceof Error) {
        onError(error);
      }
      throw error;
    } finally {
      // 清理监听器
      signal?.removeEventListener('abort', abortHandler);
    }
  },

  // 测试知识库检索
  testKnowledge: async (data: KnowledgeTestRequest): Promise<KnowledgeTestResponse> => {
    const response = await apiClient.post<KnowledgeTestResponse>('/chat/test', data);
    return response.data;
  },

  // 获取会话历史
  getHistory: async (sessionId: string, messageLimit?: number): Promise<SessionDetail> => {
    const response = await apiClient.get<SessionDetail>(`/chat/history/${sessionId}`, {
      params: { message_limit: messageLimit }
    });
    return response.data;
  },

  // 提交消息反馈
  submitFeedback: async (data: FeedbackRequest): Promise<MessageResponse> => {
    const response = await apiClient.post<MessageResponse>('/chat/feedback', data);
    return response.data;
  },
};

/**
 * 会话管理API
 */
export const sessionApi = {
  // 创建新会话
  create: async (data: SessionCreate): Promise<Session> => {
    const response = await apiClient.post<Session>('/chat/sessions', data);
    return response.data;
  },

  // 获取会话列表
  getList: async (params: {
    robot_id?: number;
    status_filter?: string;
    skip?: number;
    limit?: number;
  }): Promise<SessionListResponse> => {
    const response = await apiClient.get<SessionListResponse>('/chat/sessions', { params });
    return response.data;
  },

  // 获取会话详情
  getById: async (sessionId: string, messageLimit?: number): Promise<SessionDetail> => {
    const response = await apiClient.get<SessionDetail>(`/chat/sessions/${sessionId}`, {
      params: { message_limit: messageLimit }
    });
    return response.data;
  },

  // 更新会话
  update: async (sessionId: string, data: SessionUpdate): Promise<Session> => {
    const response = await apiClient.put<Session>(`/chat/sessions/${sessionId}`, data);
    return response.data;
  },

  // 删除会话
  delete: async (sessionId: string): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/chat/sessions/${sessionId}`);
    return response.data;
  },
};
