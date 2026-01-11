'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuthStore, useThemeStore } from '@/stores';
import { Header } from './header';

interface MainLayoutProps {
  children: React.ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, token, refreshUser } = useAuthStore();
  const { theme } = useThemeStore();
  const [mounted, setMounted] = useState(false);

  // 等待客户端挂载
  useEffect(() => {
    setMounted(true);
  }, []);

  // 主题切换
  useEffect(() => {
    if (!mounted) return;
    const root = document.documentElement;
    if (theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme, mounted]);

  // 认证检查
  useEffect(() => {
    if (!mounted) return;

    const publicPaths = ['/auth/login', '/auth/register'];
    const isPublicPath = publicPaths.some(path => pathname.startsWith(path));
    const storedToken = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

    // 如果没有认证状态且 localStorage 有 token，尝试刷新用户信息
    if (storedToken && !isAuthenticated && !isPublicPath) {
      refreshUser();
      return;
    }

    // 完全没有认证信息，跳转登录
    if (!isAuthenticated && !storedToken && !isPublicPath) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, pathname, router, refreshUser, mounted]);

  // 未挂载时显示加载状态
  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    );
  }

  // 公开页面（登录/注册）不需要布局
  if (pathname.startsWith('/auth/')) {
    return <>{children}</>;
  }

  // 未认证时显示空白
  if (!isAuthenticated) {
    // 检查 localStorage 是否有 token，如果有则显示加载（可能在刷新用户信息）
    if (typeof window !== 'undefined' && localStorage.getItem('token')) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
          <div className="text-gray-500">验证身份中...</div>
        </div>
      );
    }
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Header />
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}
