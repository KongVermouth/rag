'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { User, Shield, Trash2, Edit2, UserCheck, Key } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import { Loading, EmptyState } from '@/components/ui/loading';
import { Select } from '@/components/ui/form';
import { useAuthStore } from '@/stores/auth-store';
import { userApi } from '@/api/auth';
import type { User as UserType, UserUpdate } from '@/types';
import toast from 'react-hot-toast';

export default function AdminUsersPage() {
  const router = useRouter();
  const { user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<UserType[]>([]);
  const [loading, setLoading] = useState(true);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserType | null>(null);
  const [editForm, setEditForm] = useState<UserUpdate>({});
  const [searchTerm, setSearchTerm] = useState('');
  const [showResetModal, setShowResetModal] = useState(false);
  const [resettingUser, setResettingUser] = useState<UserType | null>(null);
  const [resetLoading, setResetLoading] = useState(false);

  useEffect(() => {
    if (currentUser?.role !== 'admin') {
      router.push('/chat');
      return;
    }
    fetchUsers();
  }, [currentUser, router]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const data = await userApi.getUsers({ limit: 100 });
      setUsers(data.items);
    } catch (error) {
      toast.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateUser = async () => {
    if (!editingUser) return;

    try {
      await userApi.updateUser(editingUser.id, editForm);
      toast.success('更新成功');
      setShowEditModal(false);
      setEditingUser(null);
      fetchUsers();
    } catch (error) {
      toast.error('更新失败');
    }
  };

  const handleDeleteUser = async (id: number) => {
    if (!confirm('确定要删除此用户吗？')) return;

    try {
      await userApi.deleteUser(id);
      toast.success('删除成功');
      fetchUsers();
    } catch (error) {
      toast.error('删除失败');
    }
  };

  const handleResetPassword = async () => {
    if (!resettingUser) return;

    setResetLoading(true);
    try {
      const result = await userApi.resetPassword(resettingUser.id);
      toast.success(`密码重置成功，新密码规则: ${result.password_rule || '请查看提示'}`);
      setShowResetModal(false);
      setResettingUser(null);
    } catch (error) {
      toast.error('密码重置失败');
    } finally {
      setResetLoading(false);
    }
  };

  const openResetModal = (user: UserType) => {
    setResettingUser(user);
    setShowResetModal(true);
  };

  const openEditModal = (user: UserType) => {
    setEditingUser(user);
    setEditForm({
      email: user.email,
      role: user.role,
      status: user.status,
    });
    setShowEditModal(true);
  };

  const filteredUsers = users.filter((u: UserType) =>
    u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  if (currentUser?.role !== 'admin') {
    return null;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">用户管理</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            管理系统用户账户
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                <User className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">总用户数</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{users.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                <UserCheck className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">活跃用户</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  {users.filter(u => u.status === 1).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
                <Shield className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">管理员</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  {users.filter(u => u.role === 'admin').length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mb-4">
        <Input
          placeholder="搜索用户名或邮箱..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-md"
        />
      </div>

      {loading ? (
        <Loading text="加载中..." />
      ) : filteredUsers.length === 0 ? (
        <EmptyState
          title="暂无用户"
          description={searchTerm ? '没有找到匹配的用户' : '系统中还没有用户'}
        />
      ) : (
        <div className="space-y-4">
          {filteredUsers.map((user) => (
            <Card key={user.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                      <User className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-gray-900 dark:text-white">
                          {user.username}
                        </h3>
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          user.role === 'admin'
                            ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300'
                            : 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
                        }`}>
                          {user.role === 'admin' ? '管理员' : '用户'}
                        </span>
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          user.status === 1
                            ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                            : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                        }`}>
                          {user.status === 1 ? '活跃' : '禁用'}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {user.email}
                      </p>
                      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                        注册时间: {formatDate(user.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openEditModal(user)}
                    >
                      <Edit2 className="w-4 h-4 mr-1" />
                      编辑
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openResetModal(user)}
                      title="重置密码"
                    >
                      <Key className="w-4 h-4 mr-1" />
                      重置密码
                    </Button>
                    {user.id !== currentUser?.id && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDeleteUser(user.id)}
                      >
                        <Trash2 className="w-4 h-4 mr-1" />
                        删除
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingUser(null);
        }}
        title="编辑用户"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              用户名
            </label>
            <Input
              value={editingUser?.username || ''}
              disabled
              className="bg-gray-100 dark:bg-gray-800"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              邮箱
            </label>
            <Input
              value={editForm.email || ''}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              角色
            </label>
            <Select
              value={editForm.role || 'user'}
              onChange={(e) => setEditForm({ ...editForm, role: e.target.value as 'user' | 'admin' })}
            >
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </Select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              状态
            </label>
            <Select
              value={editForm.status?.toString() || '1'}
              onChange={(e) => setEditForm({ ...editForm, status: parseInt(e.target.value) })}
            >
              <option value="1">活跃</option>
              <option value="0">禁用</option>
            </Select>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => {
                setShowEditModal(false);
                setEditingUser(null);
              }}
            >
              取消
            </Button>
            <Button
              className="flex-1"
              onClick={handleUpdateUser}
            >
              保存
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showResetModal}
        onClose={() => {
          setShowResetModal(false);
          setResettingUser(null);
        }}
        title="重置密码"
      >
        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-400">
            确定要重置用户 <span className="font-medium text-gray-900 dark:text-white">{resettingUser?.username}</span> 的密码吗？
          </p>
          <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm text-blue-700 dark:text-blue-300">
            <p className="font-medium mb-1">密码重置规则：</p>
            <p>新密码格式为：<code className="px-1 bg-blue-100 dark:bg-blue-800 rounded">用户名_邮箱前缀</code></p>
            <p className="mt-1 text-xs">例如：用户名为 john，邮箱为 john@example.com，则新密码为 <code className="px-1 bg-blue-100 dark:bg-blue-800 rounded">john_john</code></p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => {
                setShowResetModal(false);
                setResettingUser(null);
              }}
            >
              取消
            </Button>
            <Button
              className="flex-1"
              onClick={handleResetPassword}
              loading={resetLoading}
            >
              确认重置
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
