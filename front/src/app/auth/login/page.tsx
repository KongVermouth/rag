'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Bot, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { authApi } from '@/api';
import { useAuthStore } from '@/stores';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.username.trim()) {
      newErrors.username = '请输入用户名或邮箱';
    }
    if (!formData.password) {
      newErrors.password = '请输入密码';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    try {
      // 1. 登录获取token
      const tokenResponse = await authApi.login({
        username: formData.username,
        password: formData.password,
      });
      
      // 2. 先将 token 保存到 localStorage，这样后续请求才能携带 Authorization header
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', tokenResponse.access_token);
      }
      
      // 3. 获取用户信息（此时请求会携带 token）
      const user = await authApi.getCurrentUser();
      
      // 4. 保存到 Zustand 状态（同步状态管理）
      login(tokenResponse.access_token, user);
      
      toast.success('登录成功');
      router.push('/chat');
    } catch (error) {
      // 登录失败时清除可能残留的 token
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
      }
      const message = error instanceof Error ? error.message : '登录失败';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <Bot className="h-12 w-12 text-primary-600" />
        </div>
        <h2 className="mt-6 text-center text-3xl font-bold text-gray-900 dark:text-white">
          登录账户
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
          还没有账户？{' '}
          <Link
            href="/auth/register"
            className="font-medium text-primary-600 hover:text-primary-500"
          >
            立即注册
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white dark:bg-gray-800 py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <Input
              label="用户名或邮箱"
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              error={errors.username}
              placeholder="请输入用户名或邮箱"
            />

            <div className="relative">
              <Input
                label="密码"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                error={errors.password}
                placeholder="请输入密码"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>

            <Button type="submit" className="w-full" loading={loading}>
              登录
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
