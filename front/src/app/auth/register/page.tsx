'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Bot, Eye, EyeOff, Shield, User } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { authApi } from '@/api';
import { useAuthStore } from '@/stores/auth-store';

export default function RegisterPage() {
  const router = useRouter();
  const { user: currentUser, isAuthenticated } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: 'user' as 'user' | 'admin',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // 只有已登录的管理员才能创建管理员账户
  const canCreateAdmin = isAuthenticated && currentUser?.role === 'admin';

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.username.trim()) {
      newErrors.username = '请输入用户名';
    } else if (formData.username.length < 3) {
      newErrors.username = '用户名至少3个字符';
    }
    
    if (!formData.email.trim()) {
      newErrors.email = '请输入邮箱';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = '请输入有效的邮箱地址';
    }
    
    if (!formData.password) {
      newErrors.password = '请输入密码';
    } else if (formData.password.length < 6) {
      newErrors.password = '密码至少6个字符';
    }
    
    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = '两次输入的密码不一致';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    try {
      await authApi.register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
        // 只有管理员才能创建管理员账户
        role: canCreateAdmin ? formData.role : 'user',
      });
      
      toast.success('注册成功，请登录');
      router.push('/auth/login');
    } catch (error) {
      const message = error instanceof Error ? error.message : '注册失败';
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
          创建账户
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
          已有账户？{' '}
          <Link
            href="/auth/login"
            className="font-medium text-primary-600 hover:text-primary-500"
          >
            立即登录
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white dark:bg-gray-800 py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <form className="space-y-6" onSubmit={handleSubmit}>
            <Input
              label="用户名"
              type="text"
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              error={errors.username}
              placeholder="请输入用户名（至少3个字符）"
            />

            <Input
              label="邮箱"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              error={errors.email}
              placeholder="请输入邮箱地址"
            />

            <div className="relative">
              <Input
                label="密码"
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                error={errors.password}
                placeholder="请输入密码（至少6个字符）"
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

            <Input
              label="确认密码"
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
              error={errors.confirmPassword}
              placeholder="请再次输入密码"
            />

            {/* 角色选择 - 只有管理员可见 */}
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                用户角色
              </label>
              
              <div className="space-y-2">
                {/* 普通用户选项 */}
                <label
                  className={`flex items-center p-3 border rounded-lg cursor-pointer transition-all ${
                    formData.role === 'user'
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                  }`}
                >
                  <input
                    type="radio"
                    name="role"
                    value="user"
                    checked={formData.role === 'user'}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'user' | 'admin' })}
                    className="sr-only"
                  />
                  <div className={`flex items-center justify-center w-10 h-10 rounded-full mr-3 ${
                    formData.role === 'user' 
                      ? 'bg-primary-100 dark:bg-primary-800' 
                      : 'bg-gray-100 dark:bg-gray-700'
                  }`}>
                    <User className={`h-5 w-5 ${
                      formData.role === 'user' 
                        ? 'text-primary-600 dark:text-primary-400' 
                        : 'text-gray-500 dark:text-gray-400'
                    }`} />
                  </div>
                  <div className="flex-1">
                    <div className={`font-medium ${
                      formData.role === 'user' 
                        ? 'text-primary-700 dark:text-primary-300' 
                        : 'text-gray-900 dark:text-white'
                    }`}>
                      普通用户
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      可以创建知识库、上传文档、配置机器人、使用聊天功能
                    </div>
                  </div>
                  {formData.role === 'user' && (
                    <div className="w-4 h-4 rounded-full bg-primary-500 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-white"></div>
                    </div>
                  )}
                </label>

                {/* 管理员选项 - 只有管理员可见 */}
                {canCreateAdmin ? (
                  <label
                    className={`flex items-center p-3 border rounded-lg cursor-pointer transition-all ${
                      formData.role === 'admin'
                        ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20'
                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'
                    }`}
                  >
                    <input
                      type="radio"
                      name="role"
                      value="admin"
                      checked={formData.role === 'admin'}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value as 'user' | 'admin' })}
                      className="sr-only"
                    />
                    <div className={`flex items-center justify-center w-10 h-10 rounded-full mr-3 ${
                      formData.role === 'admin' 
                        ? 'bg-amber-100 dark:bg-amber-800' 
                        : 'bg-gray-100 dark:bg-gray-700'
                    }`}>
                      <Shield className={`h-5 w-5 ${
                        formData.role === 'admin' 
                          ? 'text-amber-600 dark:text-amber-400' 
                          : 'text-gray-500 dark:text-gray-400'
                      }`} />
                    </div>
                    <div className="flex-1">
                      <div className={`font-medium ${
                        formData.role === 'admin' 
                          ? 'text-amber-700 dark:text-amber-300' 
                          : 'text-gray-900 dark:text-white'
                      }`}>
                        管理员
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        拥有所有普通用户权限，还可以管理用户、配置LLM模型、管理API密钥
                      </div>
                    </div>
                    {formData.role === 'admin' && (
                      <div className="w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center">
                        <div className="w-2 h-2 rounded-full bg-white"></div>
                      </div>
                    )}
                  </label>
                ) : (
                  <div className="p-3 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                    <div className="flex items-center text-gray-500 dark:text-gray-400">
                      <Shield className="h-5 w-5 mr-2 opacity-50" />
                      <div>
                        <div className="text-sm font-medium">管理员角色</div>
                        <div className="text-xs">只有管理员登录后才能创建管理员账户</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <Button type="submit" className="w-full" loading={loading}>
              注册
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
