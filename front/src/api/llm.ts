import apiClient from '@/lib/api-client';
import type { 
  LLM, 
  LLMCreate, 
  LLMUpdate, 
  LLMListResponse,
  LLMBrief,
  MessageResponse 
} from '@/types';

/**
 * LLM模型管理API
 */
export const llmApi = {
  // 创建LLM模型（管理员）
  create: async (data: LLMCreate): Promise<LLM> => {
    const response = await apiClient.post<LLM>('/llms', data);
    return response.data;
  },

  // 获取LLM列表（管理员）
  getList: async (params: { skip?: number; limit?: number; model_type?: string }): Promise<LLMListResponse> => {
    const response = await apiClient.get<LLMListResponse>('/llms', { params });
    return response.data;
  },

  // 获取可用LLM选项（所有用户）
  getOptions: async (modelType?: string): Promise<LLMBrief[]> => {
    const response = await apiClient.get<LLMBrief[]>('/llms/options', { 
      params: { model_type: modelType } 
    });
    return response.data;
  },

  // 获取LLM简要列表（管理员）
  getBriefList: async (modelType?: string): Promise<LLMBrief[]> => {
    const response = await apiClient.get<LLMBrief[]>('/llms/brief', { 
      params: { model_type: modelType } 
    });
    return response.data;
  },

  // 获取LLM详情（管理员）
  getById: async (id: number): Promise<LLM> => {
    const response = await apiClient.get<LLM>(`/llms/${id}`);
    return response.data;
  },

  // 更新LLM（管理员）
  update: async (id: number, data: LLMUpdate): Promise<LLM> => {
    const response = await apiClient.put<LLM>(`/llms/${id}`, data);
    return response.data;
  },

  // 删除LLM（管理员）
  delete: async (id: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/llms/${id}`);
    return response.data;
  },
};
