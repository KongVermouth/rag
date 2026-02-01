import apiClient from '@/lib/api-client';
import type { 
  Document, 
  DocumentUploadResponse, 
  DocumentListResponse,
  DocumentStatus,
  MessageResponse 
} from '@/types';

/**
 * 文档管理API
 */
export const documentApi = {
  // 上传文档
  upload: async (knowledgeId: number, file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await apiClient.post<DocumentUploadResponse>(
      `/documents/upload?knowledge_id=${knowledgeId}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 上传超时2分钟
      }
    );
    return response.data;
  },

  // 获取文档列表
  getList: async (params: {
    knowledge_id: number;
    skip?: number;
    limit?: number;
    keyword?: string;
    status_filter?: string;
  }): Promise<DocumentListResponse> => {
    const response = await apiClient.get<DocumentListResponse>('/documents', { params });
    return response.data;
  },

  // 获取文档详情
  getById: async (id: number): Promise<Document> => {
    const response = await apiClient.get<Document>(`/documents/${id}`);
    return response.data;
  },

  // 获取文档处理状态
  getStatus: async (id: number): Promise<DocumentStatus> => {
    const response = await apiClient.get<DocumentStatus>(`/documents/${id}/status`);
    return response.data;
  },

  // 删除文档
  delete: async (id: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/documents/${id}`);
    return response.data;
  },

  // 重试文档处理
  retry: async (id: number): Promise<{ code: number; message: string; data: any }> => {
    const response = await apiClient.post<{ code: number; message: string; data: any }>(`/documents/${id}/retry`);
    return response.data;
  },
};
