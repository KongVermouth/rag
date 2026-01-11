import apiClient from '@/lib/api-client';
import type { 
  Robot, 
  RobotCreate, 
  RobotUpdate, 
  RobotListResponse,
  RobotBrief,
  MessageResponse 
} from '@/types';

/**
 * 机器人管理API
 */
export const robotApi = {
  // 创建机器人
  create: async (data: RobotCreate): Promise<Robot> => {
    const response = await apiClient.post<Robot>('/robots', data);
    return response.data;
  },

  // 获取机器人列表
  getList: async (params: { skip?: number; limit?: number; keyword?: string }): Promise<RobotListResponse> => {
    const response = await apiClient.get<RobotListResponse>('/robots', { params });
    return response.data;
  },

  // 获取机器人简要列表（下拉选择）
  getBriefList: async (): Promise<RobotBrief[]> => {
    const response = await apiClient.get<RobotBrief[]>('/robots/brief');
    return response.data;
  },

  // 获取机器人详情
  getById: async (id: number): Promise<Robot> => {
    const response = await apiClient.get<Robot>(`/robots/${id}`);
    return response.data;
  },

  // 更新机器人
  update: async (id: number, data: RobotUpdate): Promise<Robot> => {
    const response = await apiClient.put<Robot>(`/robots/${id}`, data);
    return response.data;
  },

  // 删除机器人
  delete: async (id: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/robots/${id}`);
    return response.data;
  },
};
