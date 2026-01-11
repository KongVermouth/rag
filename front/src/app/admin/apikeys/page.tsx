'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Key, Plus, Copy, Trash2, Eye, EyeOff, Edit2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Modal } from '@/components/ui/modal';
import { Loading, EmptyState } from '@/components/ui/loading';
import { Select, Textarea } from '@/components/ui/form';
import { useAuthStore } from '@/stores/auth-store';
import { apiKeyApi } from '@/api/apikey';
import { llmApi } from '@/api/llm';
import type { APIKey, APIKeyCreate, APIKeyUpdate, LLM } from '@/types';
import toast from 'react-hot-toast';

export default function APIKeysPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [llms, setLlms] = useState<LLM[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingKey, setEditingKey] = useState<APIKey | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<number, boolean>>({});

  const [formData, setFormData] = useState<APIKeyCreate>({
    llm_id: 0,
    alias: '',
    api_key: '',
    description: '',
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (user?.role !== 'admin') {
      router.push('/chat');
      return;
    }
    fetchData();
  }, [user, router]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [keysRes, llmsRes] = await Promise.all([
        apiKeyApi.getList({ limit: 100 }),
        llmApi.getList({ limit: 100 }),
      ]);
      setApiKeys(keysRes.items);
      setLlms(llmsRes.items);
    } catch (error) {
      toast.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.llm_id) {
      toast.error('请选择LLM模型');
      return;
    }
    if (!formData.alias.trim()) {
      toast.error('请输入密钥别名');
      return;
    }
    if (!formData.api_key.trim()) {
      toast.error('请输入API密钥');
      return;
    }

    try {
      setCreating(true);
      await apiKeyApi.create(formData);
      toast.success('API密钥创建成功');
      setShowCreateModal(false);
      setFormData({ llm_id: 0, alias: '', api_key: '', description: '' });
      fetchData();
    } catch (error) {
      toast.error('创建失败');
    } finally {
      setCreating(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingKey) return;

    try {
      const updateData: APIKeyUpdate = {
        alias: formData.alias,
        description: formData.description,
      };
      if (formData.api_key) {
        updateData.api_key = formData.api_key;
      }
      await apiKeyApi.update(editingKey.id, updateData);
      toast.success('更新成功');
      setShowEditModal(false);
      setEditingKey(null);
      fetchData();
    } catch (error) {
      toast.error('更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除此API密钥吗？删除后将无法恢复。')) return;

    try {
      await apiKeyApi.delete(id);
      toast.success('删除成功');
      fetchData();
    } catch (error) {
      toast.error('删除失败');
    }
  };

  const openEditModal = (apiKey: APIKey) => {
    setEditingKey(apiKey);
    setFormData({
      llm_id: apiKey.llm_id,
      alias: apiKey.alias,
      api_key: '',
      description: apiKey.description || '',
    });
    setShowEditModal(true);
  };

  const toggleKeyVisibility = (id: number) => {
    setVisibleKeys((prev: Record<number, boolean>) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('已复制到剪贴板');
  };

  const getLlmName = (llmId: number) => {
    const llm = llms.find(l => l.id === llmId);
    return llm?.name || '未知模型';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  if (user?.role !== 'admin') {
    return null;
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">API密钥管理</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            管理LLM模型的API访问密钥
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          添加密钥
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                <Key className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">总密钥数</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">{apiKeys.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
                <Key className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">活跃密钥</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  {apiKeys.filter(k => k.status === 1).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
                <Key className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">关联模型</p>
                <p className="text-xl font-bold text-gray-900 dark:text-white">
                  {new Set(apiKeys.map(k => k.llm_id)).size}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {loading ? (
        <Loading text="加载中..." />
      ) : apiKeys.length === 0 ? (
        <EmptyState
          title="暂无API密钥"
          description="点击上方按钮添加第一个API密钥"
        />
      ) : (
        <div className="space-y-4">
          {apiKeys.map((apiKey) => (
            <Card key={apiKey.id}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium text-gray-900 dark:text-white">
                        {apiKey.alias}
                      </h3>
                      <span className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded">
                        {getLlmName(apiKey.llm_id)}
                      </span>
                      <span className={`px-2 py-0.5 text-xs rounded-full ${
                        apiKey.status === 1
                          ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                          : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                      }`}>
                        {apiKey.status === 1 ? '活跃' : '已禁用'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <code className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono">
                        {visibleKeys[apiKey.id] ? apiKey.api_key_masked : '••••••••••••••••'}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleKeyVisibility(apiKey.id)}
                      >
                        {visibleKeys[apiKey.id] ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyToClipboard(apiKey.api_key_masked)}
                      >
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                    {apiKey.description && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                        {apiKey.description}
                      </p>
                    )}
                    <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                      创建时间: {formatDate(apiKey.created_at)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => openEditModal(apiKey)}
                    >
                      <Edit2 className="w-4 h-4 mr-1" />
                      编辑
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleDelete(apiKey.id)}
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                      删除
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setFormData({ llm_id: 0, alias: '', api_key: '', description: '' });
        }}
        title="添加API密钥"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              LLM模型 *
            </label>
            <Select
              value={formData.llm_id.toString()}
              onChange={(e) => setFormData({ ...formData, llm_id: parseInt(e.target.value) })}
            >
              <option value="0">请选择模型</option>
              {llms.map((llm) => (
                <option key={llm.id} value={llm.id}>
                  {llm.name} ({llm.provider} - {llm.model_type})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              密钥别名 *
            </label>
            <Input
              value={formData.alias}
              onChange={(e) => setFormData({ ...formData, alias: e.target.value })}
              placeholder="例如：生产环境密钥"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              API密钥 *
            </label>
            <Input
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder="输入API密钥"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              描述
            </label>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="可选的密钥描述"
              rows={2}
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => {
                setShowCreateModal(false);
                setFormData({ llm_id: 0, alias: '', api_key: '', description: '' });
              }}
            >
              取消
            </Button>
            <Button
              className="flex-1"
              onClick={handleCreate}
              disabled={creating}
            >
              {creating ? '添加中...' : '添加'}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingKey(null);
        }}
        title="编辑API密钥"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              密钥别名 *
            </label>
            <Input
              value={formData.alias}
              onChange={(e) => setFormData({ ...formData, alias: e.target.value })}
              placeholder="例如：生产环境密钥"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              新API密钥（留空保持不变）
            </label>
            <Input
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
              placeholder="输入新的API密钥"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              描述
            </label>
            <Textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="可选的密钥描述"
              rows={2}
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => {
                setShowEditModal(false);
                setEditingKey(null);
              }}
            >
              取消
            </Button>
            <Button
              className="flex-1"
              onClick={handleUpdate}
            >
              保存
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
