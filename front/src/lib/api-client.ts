import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加认证Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 客户端环境下获取token
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// 自定义错误类，包含状态码
export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data as { detail?: string; msg?: string };
      
      // 401 未授权 - 清除token并跳转到登录页
      if (status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          // 如果不在登录页，跳转到登录页
          if (!window.location.pathname.includes('/auth')) {
            window.location.href = '/auth/login';
          }
        }
      }
      
      // 提取错误信息
      const errorMessage = data?.msg || data?.detail || getDefaultErrorMessage(status);
      return Promise.reject(new ApiError(errorMessage, status, data));
    }
    
    // 网络错误
    if (error.message === 'Network Error') {
      return Promise.reject(new ApiError('网络连接失败，请检查网络', 0));
    }
    
    // 超时
    if (error.code === 'ECONNABORTED') {
      return Promise.reject(new ApiError('请求超时，请重试', 408));
    }
    
    return Promise.reject(error);
  }
);

// 默认错误信息
function getDefaultErrorMessage(status: number): string {
  const messages: Record<number, string> = {
    400: '请求参数错误',
    401: '未授权，请登录',
    403: '没有权限执行此操作',
    404: '请求的资源不存在',
    422: '请求数据验证失败',
    500: '服务器内部错误',
    502: '服务器网关错误',
    503: '服务暂时不可用',
  };
  return messages[status] || '请求失败';
}

export default apiClient;
