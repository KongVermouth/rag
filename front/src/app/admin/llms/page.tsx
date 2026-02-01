'use client';

import { useState, useEffect, useRef } from 'react';
import { Plus, Search, Settings, Trash2, Edit2, Filter } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button, Input } from '@/components/ui';
import { PageLoading, EmptyState } from '@/components/ui/loading';
import { Modal, ConfirmModal } from '@/components/ui/modal';
import { Select, Textarea } from '@/components/ui/form';
import { formatDateTime } from '@/lib/utils';
import { llmApi } from '@/api';
import type { LLM, LLMCreate, LLMUpdate } from '@/types';

export default function LLMsAdminPage() {
  const [llms, setLLMs] = useState<LLM[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedLLM, setSelectedLLM] = useState<LLM | null>(null);
  const [modelTypeFilter, setModelTypeFilter] = useState<string>('');
  const [formLoading, setFormLoading] = useState(false);

  const [formData, setFormData] = useState<LLMCreate>({
    name: '',
    model_type: 'chat',
    provider: 'openai',
    model_name: '',
    base_url: '',
    description: '',
  });
  const [editFormData, setEditFormData] = useState<LLMUpdate>({});

  // 初始加载
  useEffect(() => {
    loadLLMs(modelTypeFilter);
  }, []);

  const loadLLMs = async (filter?: string) => {
    setLoading(true);
    try {
      const data = await llmApi.getList({ limit: 100, model_type: filter || undefined });
      setLLMs(data.items);
    } catch (error) {
      toast.error('加载LLM列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleModelTypeChange = (value: string) => {
    setModelTypeFilter(value);
    loadLLMs(value);
  };

  const handleCreate = async () => {
    if (!formData.name.trim() || !formData.model_name.trim()) {
      toast.error('请填写必要信息');
      return;
    }
    setFormLoading(true);
    try {
      await llmApi.create(formData);
      toast.success('LLM创建成功');
      setShowCreateModal(false);
      resetForm();
      loadLLMs();
    } catch (error) {
      const message = error instanceof Error ? error.message : '创建失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedLLM) return;
    setFormLoading(true);
    try {
      await llmApi.delete(selectedLLM.id);
      toast.success('LLM删除成功');
      setShowDeleteModal(false);
      setSelectedLLM(null);
      loadLLMs();
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedLLM) return;
    setFormLoading(true);
    try {
      await llmApi.update(selectedLLM.id, editFormData);
      toast.success('LLM更新成功');
      setShowEditModal(false);
      setSelectedLLM(null);
      loadLLMs();
    } catch (error) {
      const message = error instanceof Error ? error.message : '更新失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const openEditModal = (llm: LLM) => {
    setSelectedLLM(llm);
    setEditFormData({
      name: llm.name,
      base_url: llm.base_url,
      description: llm.description,
      status: llm.status,
    });
    setShowEditModal(true);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      model_type: 'chat',
      provider: 'openai',
      model_name: '',
      base_url: '',
      description: '',
    });
  };

  if (loading) return <PageLoading />;

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">LLM配置</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">管理LLM模型配置</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <Select
              value={modelTypeFilter}
              onChange={(e) => handleModelTypeChange(e.target.value)}
              className="w-36"
            >
              <option value="">全部类型</option>
              <option value="chat">对话模型</option>
              <option value="embedding">嵌入模型</option>
              <option value="rerank">重排序模型</option>
            </Select>
          </div>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            添加LLM
          </Button>
        </div>
      </div>

      {llms.length === 0 ? (
        <EmptyState
          icon={<Settings className="h-12 w-12" />}
          title="暂无LLM配置"
          action={<Button onClick={() => setShowCreateModal(true)}>添加LLM</Button>}
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">提供商</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">模型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">创建时间</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {llms.map((llm) => (
                <tr key={llm.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-white">{llm.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      llm.model_type === 'chat' ? 'bg-blue-100 text-blue-800' : 
                      llm.model_type === 'embedding' ? 'bg-purple-100 text-purple-800' :
                      'bg-orange-100 text-orange-800'
                    }`}>
                      {llm.model_type === 'chat' ? '对话' : 
                       llm.model_type === 'embedding' ? '嵌入' : '重排'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{llm.provider}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{llm.model_name}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      llm.status === 1 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {llm.status === 1 ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDateTime(llm.created_at)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button
                      onClick={() => openEditModal(llm)}
                      className="text-gray-400 hover:text-primary-600 mr-3"
                      title="编辑"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => { setSelectedLLM(llm); setShowDeleteModal(true); }}
                      className="text-gray-400 hover:text-red-600"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={showCreateModal} onClose={() => setShowCreateModal(false)} title="添加LLM" size="md">
        <div className="space-y-4">
          <Input label="名称" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="如: GPT-4" />
          <Select label="类型" value={formData.model_type} onChange={(e) => setFormData({ ...formData, model_type: e.target.value as 'chat' | 'embedding' | 'rerank' })}
            options={[
              { value: 'chat', label: '对话模型' },
              { value: 'embedding', label: 'Embedding模型' },
              { value: 'rerank', label: '重排序模型' }
            ]} />
          <Input label="提供商" value={formData.provider} onChange={(e) => setFormData({ ...formData, provider: e.target.value })} placeholder="openai / azure / local" />
          <Input label="模型标识" value={formData.model_name} onChange={(e) => setFormData({ ...formData, model_name: e.target.value })} placeholder="gpt-4 / text-embedding-ada-002" />
          <Input label="Base URL (可选)" value={formData.base_url || ''} onChange={(e) => setFormData({ ...formData, base_url: e.target.value })} placeholder="API基础地址" />
          <Textarea label="描述 (可选)" value={formData.description || ''} onChange={(e) => setFormData({ ...formData, description: e.target.value })} rows={2} />
          <div className="flex justify-end space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>取消</Button>
            <Button onClick={handleCreate} loading={formLoading}>创建</Button>
          </div>
        </div>
      </Modal>

      {/* 编辑LLM弹窗 */}
      <Modal isOpen={showEditModal} onClose={() => setShowEditModal(false)} title="编辑LLM" size="md">
        <div className="space-y-4">
          <Input label="名称" value={editFormData.name || ''} onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })} placeholder="如: GPT-4" />
          <Input label="Base URL (可选)" value={editFormData.base_url || ''} onChange={(e) => setEditFormData({ ...editFormData, base_url: e.target.value })} placeholder="API基础地址" />
          <Select
            label="状态"
            value={editFormData.status || 1}
            onChange={(e) => setEditFormData({ ...editFormData, status: parseInt(e.target.value) })}
            options={[{ value: 1, label: '启用' }, { value: 0, label: '禁用' }]}
          />
          <Textarea label="描述 (可选)" value={editFormData.description || ''} onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })} rows={2} />
          <div className="flex justify-end space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowEditModal(false)}>取消</Button>
            <Button onClick={handleUpdate} loading={formLoading}>保存</Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal isOpen={showDeleteModal} onClose={() => setShowDeleteModal(false)} onConfirm={handleDelete}
        title="删除LLM" message={`确定要删除"${selectedLLM?.name}"吗？`} confirmText="删除" variant="danger" loading={formLoading} />
    </div>
  );
}
