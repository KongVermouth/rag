'use client';

import { useState, useEffect } from 'react';
import { Plus, Search, Bot, Settings, Trash2, Edit2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button, Input, Card, CardContent } from '@/components/ui';
import { PageLoading, EmptyState } from '@/components/ui/loading';
import { Modal, ConfirmModal } from '@/components/ui/modal';
import { Select, Textarea } from '@/components/ui/form';
import { formatDateTime } from '@/lib/utils';
import { robotApi, knowledgeApi, llmApi } from '@/api';
import type { Robot, RobotCreate, RobotUpdate, KnowledgeBrief, LLMBrief } from '@/types';

export default function RobotsPage() {
  const [robots, setRobots] = useState<Robot[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchKeyword, setSearchKeyword] = useState('');
  
  // 弹窗状态
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedRobot, setSelectedRobot] = useState<Robot | null>(null);
  
  // 表单数据
  const [formData, setFormData] = useState<RobotCreate>({
    name: '',
    chat_llm_id: 0,
    knowledge_ids: [],
    system_prompt: '你是一个智能助手，请基于提供的知识库内容回答用户问题。',
    top_k: 5,
    temperature: 0.7,
    max_tokens: 2000,
    description: '',
  });
  const [chatModels, setChatModels] = useState<LLMBrief[]>([]);
  const [knowledges, setKnowledges] = useState<KnowledgeBrief[]>([]);
  const [formLoading, setFormLoading] = useState(false);
  
  // 编辑表单数据
  const [editFormData, setEditFormData] = useState<RobotUpdate>({});

  useEffect(() => {
    loadRobots();
    loadOptions();
  }, []);

  const loadRobots = async (keyword?: string) => {
    setLoading(true);
    try {
      const data = await robotApi.getList({ keyword, limit: 100 });
      setRobots(data.items);
    } catch (error) {
      toast.error('加载机器人列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadOptions = async () => {
    try {
      const [models, kbs] = await Promise.all([
        llmApi.getOptions('chat'),
        knowledgeApi.getBriefList(),
      ]);
      setChatModels(models);
      setKnowledges(kbs);
      if (models.length > 0) {
        setFormData(prev => ({ ...prev, chat_llm_id: models[0].id }));
      }
    } catch (error) {
      console.error('加载选项失败', error);
    }
  };

  const handleSearch = () => {
    loadRobots(searchKeyword);
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error('请输入机器人名称');
      return;
    }
    if (!formData.chat_llm_id) {
      toast.error('请选择对话模型');
      return;
    }
    if (formData.knowledge_ids.length === 0) {
      toast.error('请至少选择一个知识库');
      return;
    }

    setFormLoading(true);
    try {
      await robotApi.create(formData);
      toast.success('机器人创建成功');
      setShowCreateModal(false);
      resetForm();
      loadRobots();
    } catch (error) {
      const message = error instanceof Error ? error.message : '创建失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedRobot) return;
    
    setFormLoading(true);
    try {
      await robotApi.delete(selectedRobot.id);
      toast.success('机器人删除成功');
      setShowDeleteModal(false);
      setSelectedRobot(null);
      loadRobots();
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedRobot) return;
    
    setFormLoading(true);
    try {
      await robotApi.update(selectedRobot.id, editFormData);
      toast.success('机器人更新成功');
      setShowEditModal(false);
      setSelectedRobot(null);
      loadRobots();
    } catch (error) {
      const message = error instanceof Error ? error.message : '更新失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      chat_llm_id: chatModels[0]?.id || 0,
      knowledge_ids: [],
      system_prompt: '你是一个智能助手，请基于提供的知识库内容回答用户问题。',
      top_k: 5,
      temperature: 0.7,
      max_tokens: 2000,
      description: '',
    });
  };

  const openEditModal = (robot: Robot) => {
    setSelectedRobot(robot);
    setEditFormData({
      name: robot.name,
      chat_llm_id: robot.chat_llm_id,
      knowledge_ids: robot.knowledge_ids,
      system_prompt: robot.system_prompt,
      top_k: robot.top_k,
      temperature: robot.temperature,
      max_tokens: robot.max_tokens,
      description: robot.description,
    });
    setShowEditModal(true);
  };

  const toggleKnowledge = (id: number) => {
    setFormData(prev => ({
      ...prev,
      knowledge_ids: prev.knowledge_ids.includes(id)
        ? prev.knowledge_ids.filter(k => k !== id)
        : [...prev.knowledge_ids, id]
    }));
  };

  const toggleEditKnowledge = (id: number) => {
    setEditFormData(prev => ({
      ...prev,
      knowledge_ids: prev.knowledge_ids?.includes(id)
        ? prev.knowledge_ids.filter(k => k !== id)
        : [...(prev.knowledge_ids || []), id]
    }));
  };

  if (loading) {
    return <PageLoading />;
  }

  return (
    <div className="container mx-auto px-4 py-6">
      {/* 页面标题 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">机器人管理</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">创建和配置对话机器人</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建机器人
        </Button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索机器人..."
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
            />
          </div>
        </div>
        <Button variant="secondary" onClick={handleSearch}>
          搜索
        </Button>
      </div>

      {/* 机器人列表 */}
      {robots.length === 0 ? (
        <EmptyState
          icon={<Bot className="h-12 w-12" />}
          title="暂无机器人"
          description="创建第一个机器人开始对话"
          action={
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              新建机器人
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {robots.map((robot) => (
            <Card key={robot.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="h-10 w-10 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                      <Bot className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div className="ml-3">
                      <h3 className="font-medium text-gray-900 dark:text-white">{robot.name}</h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {robot.knowledge_ids.length} 个知识库
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => openEditModal(robot)}
                      className="p-1.5 text-gray-400 hover:text-primary-600 transition-colors"
                      title="编辑"
                    >
                      <Edit2 className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => {
                        setSelectedRobot(robot);
                        setShowDeleteModal(true);
                      }}
                      className="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                
                {robot.description && (
                  <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {robot.description}
                  </p>
                )}
                
                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                    <span>Top-K: {robot.top_k} | 温度: {robot.temperature}</span>
                    <span>{formatDateTime(robot.created_at)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 创建机器人弹窗 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="新建机器人"
        size="lg"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
          <Input
            label="机器人名称"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="请输入机器人名称"
          />
          
          <Select
            label="对话模型"
            value={formData.chat_llm_id}
            onChange={(e) => setFormData({ ...formData, chat_llm_id: parseInt(e.target.value) })}
            options={chatModels.map(m => ({ value: m.id, label: m.name }))}
          />
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              关联知识库
            </label>
            <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg p-3">
              {knowledges.map((kb) => (
                <label
                  key={kb.id}
                  className="flex items-center space-x-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={formData.knowledge_ids.includes(kb.id)}
                    onChange={() => toggleKnowledge(kb.id)}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{kb.name}</span>
                </label>
              ))}
            </div>
          </div>
          
          <Textarea
            label="系统提示词"
            value={formData.system_prompt}
            onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
            rows={3}
          />
          
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Top-K"
              type="number"
              value={formData.top_k}
              onChange={(e) => setFormData({ ...formData, top_k: parseInt(e.target.value) || 5 })}
            />
            <Input
              label="温度"
              type="number"
              step="0.1"
              value={formData.temperature}
              onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) || 0.7 })}
            />
            <Input
              label="最大Token"
              type="number"
              value={formData.max_tokens}
              onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) || 2000 })}
            />
          </div>
          
          <Textarea
            label="描述（可选）"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="请输入机器人描述"
            rows={2}
          />
          
          <div className="flex justify-end space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>
              取消
            </Button>
            <Button onClick={handleCreate} loading={formLoading}>
              创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* 编辑机器人弹窗 */}
      <Modal
        isOpen={showEditModal}
        onClose={() => setShowEditModal(false)}
        title="编辑机器人"
        size="lg"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
          <Input
            label="机器人名称"
            value={editFormData.name || ''}
            onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
            placeholder="请输入机器人名称"
          />
          
          <Select
            label="对话模型"
            value={editFormData.chat_llm_id || 0}
            onChange={(e) => setEditFormData({ ...editFormData, chat_llm_id: parseInt(e.target.value) })}
            options={chatModels.map(m => ({ value: m.id, label: m.name }))}
          />
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              关联知识库
            </label>
            <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg p-3">
              {knowledges.map((kb) => (
                <label key={kb.id} className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={editFormData.knowledge_ids?.includes(kb.id) || false}
                    onChange={() => toggleEditKnowledge(kb.id)}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">{kb.name}</span>
                </label>
              ))}
            </div>
          </div>
          
          <Textarea
            label="系统提示词"
            value={editFormData.system_prompt || ''}
            onChange={(e) => setEditFormData({ ...editFormData, system_prompt: e.target.value })}
            rows={3}
          />
          
          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Top-K"
              type="number"
              value={editFormData.top_k || 5}
              onChange={(e) => setEditFormData({ ...editFormData, top_k: parseInt(e.target.value) || 5 })}
            />
            <Input
              label="温度"
              type="number"
              step="0.1"
              value={editFormData.temperature || 0.7}
              onChange={(e) => setEditFormData({ ...editFormData, temperature: parseFloat(e.target.value) || 0.7 })}
            />
            <Input
              label="最大Token"
              type="number"
              value={editFormData.max_tokens || 2000}
              onChange={(e) => setEditFormData({ ...editFormData, max_tokens: parseInt(e.target.value) || 2000 })}
            />
          </div>
          
          <Textarea
            label="描述（可选）"
            value={editFormData.description || ''}
            onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
            placeholder="请输入机器人描述"
            rows={2}
          />
          
          <div className="flex justify-end space-x-3 pt-4">
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              取消
            </Button>
            <Button onClick={handleUpdate} loading={formLoading}>
              保存
            </Button>
          </div>
        </div>
      </Modal>

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        title="删除机器人"
        message={`确定要删除机器人"${selectedRobot?.name}"吗？`}
        confirmText="删除"
        variant="danger"
        loading={formLoading}
      />
    </div>
  );
}
