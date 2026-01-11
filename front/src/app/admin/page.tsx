'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { MainLayout } from '@/components/layout/main-layout';
import { Card, CardContent } from '@/components/ui/card';
import { Users, Key, Cpu, Settings } from 'lucide-react';
import Link from 'next/link';

export default function AdminPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  useEffect(() => {
    if (user?.role !== 'admin') {
      router.push('/chat');
    }
  }, [user, router]);

  if (user?.role !== 'admin') {
    return null;
  }

  const adminModules = [
    {
      title: '用户管理',
      description: '管理系统用户、权限设置',
      icon: Users,
      href: '/admin/users',
      color: 'text-blue-600 dark:text-blue-400',
      bgColor: 'bg-blue-100 dark:bg-blue-900',
    },
    {
      title: 'LLM模型配置',
      description: '配置大语言模型参数',
      icon: Cpu,
      href: '/admin/llms',
      color: 'text-green-600 dark:text-green-400',
      bgColor: 'bg-green-100 dark:bg-green-900',
    },
    {
      title: 'API密钥管理',
      description: '管理模型API访问密钥',
      icon: Key,
      href: '/admin/apikeys',
      color: 'text-purple-600 dark:text-purple-400',
      bgColor: 'bg-purple-100 dark:bg-purple-900',
    },
  ];

  return (
    <MainLayout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">管理员控制台</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            系统管理与配置
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {adminModules.map((module) => (
            <Link key={module.href} href={module.href}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                <CardContent className="p-6">
                  <div className={`w-12 h-12 ${module.bgColor} rounded-lg flex items-center justify-center mb-4`}>
                    <module.icon className={`w-6 h-6 ${module.color}`} />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    {module.title}
                  </h3>
                  <p className="text-gray-600 dark:text-gray-400 text-sm">
                    {module.description}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </MainLayout>
  );
}
