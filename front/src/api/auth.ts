import apiClient from '@/lib/api-client';
import type { 
  User, 
  UserRegister, 
  UserLogin, 
  TokenResponse, 
  UserUpdate, 
  UserListResponse,
  PasswordChange,
  MessageResponse 
} from '@/types';

/**
 * 认证相关API
 */
export const authApi = {
  // 用户注册
  register: async (data: UserRegister): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', data);
    return response.data;
  },

  // 用户登录
  login: async (data: UserLogin): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/login', data);
    return response.data;
  },

  // 获取当前用户信息
  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  // 刷新Token
  refreshToken: async (): Promise<TokenResponse> => {
    const response = await apiClient.post<TokenResponse>('/auth/refresh');
    return response.data;
  },
};

/**
 * 用户管理API（管理员）
 */
export const userApi = {
  // 获取用户列表
  getUsers: async (params: { skip?: number; limit?: number; keyword?: string }): Promise<UserListResponse> => {
    const response = await apiClient.get<UserListResponse>('/users', { params });
    return response.data;
  },

  // 获取用户详情
  getUser: async (userId: number): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${userId}`);
    return response.data;
  },

  // 更新用户信息
  updateUser: async (userId: number, data: UserUpdate): Promise<User> => {
    const response = await apiClient.put<User>(`/users/${userId}`, data);
    return response.data;
  },

  // 删除用户
  deleteUser: async (userId: number): Promise<MessageResponse> => {
    const response = await apiClient.delete<MessageResponse>(`/users/${userId}`);
    return response.data;
  },

  // 修改当前用户密码
  changePassword: async (data: PasswordChange): Promise<MessageResponse> => {
    const response = await apiClient.post<MessageResponse>('/users/me/change-password', data);
    return response.data;
  },

  // 重置用户密码
  resetPassword: async (userId: number): Promise<MessageResponse> => {
    const response = await apiClient.post<MessageResponse>(`/users/${userId}/reset-password`);
    return response.data;
  },
};
