import apiClient from '@/lib/api-client';
import type { RecallTestRequest, RecallTestStatusResponse } from '@/types';

export const recallApi = {
  /**
   * 提交召回测试任务
   */
  startTest: async (data: RecallTestRequest): Promise<{ taskId: string }> => {
    const response = await apiClient.post('/recall/test', data);
    return response.data;
  },

  /**
   * 获取召回测试状态
   */
  getStatus: async (taskId: string): Promise<RecallTestStatusResponse> => {
    const response = await apiClient.get(`/recall/status/${taskId}`);
    return response.data;
  },
};
