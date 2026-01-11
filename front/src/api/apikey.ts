import apiClient from '@/lib/api-client';
import type { 
  APIKey, 
  APIKeyCreate, 
  APIKeyUpdate, 
  APIKeyListResponse,
  APIKeyOptionsResponse,
  MessageResponse 
} from '@/types';

/**
 * API密钥管理API
 */
export const apiKeyApi = {
  // 创建API Key（管理员）
  create: async (data: APIKeyCreate): Promise<APIKey> => {
    const response = await apiClient.post<APIKey>('/apikeys', data);
    return response.data;
  },

  // 获取API Key列表（管理员）
  getList: async (params: { skip?: number; limit?: number; llm_id?: number }): Promise<APIKeyListResponse> => {
    const response = await apiClient.get<APIKeyListResponse>('/apikeys', { params });
    return response.data;
  },

  // 获取可用API Key选项（所有用户）
  getOptions: async (llmId?: number): Promise<APIKeyOptionsResponse> => {
    const response = await apiClient.get<APIKeyOptionsResponse>('/apikeys/options', { 
      params: { llm_id: llmId } 
    });
    return response.data;
  },

  // 获取API Key详情（管理员）
  getById: async (id: number): Promise<APIKey> => {
    const response = await apiClient.get<APIKey>(`/apikeys/${id}`);
    return response.data;
  },

  // 更新API Key（管理员）
  update: async (id: number, data: APIKeyUpdate): Promise<APIKey> => {
    const response = await apiClient.put<APIKey>(`/apikeys/${id}`, data);
    return response.data;
  },

  // 删除API Key（管理员）
  delete: async (id: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/apikeys/${id}`);
    return response.data;
  },
};
