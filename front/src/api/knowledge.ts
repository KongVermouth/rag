import apiClient from '@/lib/api-client';
import type { 
  Knowledge, 
  KnowledgeCreate, 
  KnowledgeUpdate, 
  KnowledgeListResponse,
  KnowledgeBrief,
  MessageResponse 
} from '@/types';

/**
 * 知识库管理API
 */
export const knowledgeApi = {
  // 创建知识库
  create: async (data: KnowledgeCreate): Promise<Knowledge> => {
    const response = await apiClient.post<Knowledge>('/knowledge', data);
    return response.data;
  },

  // 获取知识库列表
  getList: async (params: { skip?: number; limit?: number; keyword?: string }): Promise<KnowledgeListResponse> => {
    const response = await apiClient.get<KnowledgeListResponse>('/knowledge', { params });
    return response.data;
  },

  // 获取知识库简要列表（下拉选择）
  getBriefList: async (): Promise<KnowledgeBrief[]> => {
    const response = await apiClient.get<KnowledgeBrief[]>('/knowledge/brief');
    return response.data;
  },

  // 获取知识库详情
  getById: async (id: number): Promise<Knowledge> => {
    const response = await apiClient.get<Knowledge>(`/knowledge/${id}`);
    return response.data;
  },

  // 更新知识库
  update: async (id: number, data: KnowledgeUpdate): Promise<Knowledge> => {
    const response = await apiClient.put<Knowledge>(`/knowledge/${id}`, data);
    return response.data;
  },

  // 删除知识库
  delete: async (id: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/knowledge/${id}`);
    return response.data;
  },
};
