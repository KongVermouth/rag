import apiClient from '@/lib/api-client';

export const healthApi = {
  checkES: async () => {
    try {
      const response = await apiClient.get('/health/es');
      return response.data;
    } catch (error) {
      throw error;
    }
  }
};
