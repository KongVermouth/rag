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
  MessageResponse
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
