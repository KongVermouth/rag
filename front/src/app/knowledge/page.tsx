'use client';

import { useState, useEffect } from 'react';
import { Plus, Search, Database, FileText, Trash2, Edit, MoreVertical } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button, Input, Card, CardContent } from '@/components/ui';
import { PageLoading, EmptyState } from '@/components/ui/loading';
import { Modal, ConfirmModal } from '@/components/ui/modal';
import { Select, Textarea } from '@/components/ui/form';
import { cn, formatDateTime } from '@/lib/utils';
import { knowledgeApi, llmApi } from '@/api';
import type { Knowledge, KnowledgeCreate, LLMBrief } from '@/types';

export default function KnowledgePage() {
  const [knowledges, setKnowledges] = useState<Knowledge[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [total, setTotal] = useState(0);
  
  // 弹窗状态
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedKnowledge, setSelectedKnowledge] = useState<Knowledge | null>(null);
  
  // 表单状态
  const [formData, setFormData] = useState<KnowledgeCreate>({
    name: '',
    embed_llm_id: 0,
    chunk_size: 500,
    chunk_overlap: 50,
    description: '',
  });
  const [embeddingModels, setEmbeddingModels] = useState<LLMBrief[]>([]);
  const [formLoading, setFormLoading] = useState(false);

  useEffect(() => {
    loadKnowledges();
    loadEmbeddingModels();
  }, []);

  const loadKnowledges = async (keyword?: string) => {
    setLoading(true);
    try {
      const data = await knowledgeApi.getList({ keyword, limit: 100 });
      setKnowledges(data.items);
      setTotal(data.total);
    } catch (error) {
      toast.error('加载知识库列表失败');
    } finally {
      setLoading(false);
    }
  };

  const loadEmbeddingModels = async () => {
    try {
      const data = await llmApi.getOptions('embedding');
      setEmbeddingModels(data);
      if (data.length > 0) {
        setFormData(prev => ({ ...prev, embed_llm_id: data[0].id }));
      }
    } catch (error) {
      console.error('加载Embedding模型失败', error);
    }
  };

  const handleSearch = () => {
    loadKnowledges(searchKeyword);
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error('请输入知识库名称');
      return;
    }
    if (!formData.embed_llm_id) {
      toast.error('请选择Embedding模型');
      return;
    }

    setFormLoading(true);
    try {
      await knowledgeApi.create(formData);
      toast.success('知识库创建成功');
      setShowCreateModal(false);
      resetForm();
      loadKnowledges();
    } catch (error) {
      const message = error instanceof Error ? error.message : '创建失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedKnowledge) return;
    
    setFormLoading(true);
    try {
      await knowledgeApi.delete(selectedKnowledge.id);
      toast.success('知识库删除成功');
      setShowDeleteModal(false);
      setSelectedKnowledge(null);
      loadKnowledges();
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      toast.error(message);
    } finally {
      setFormLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '',
      embed_llm_id: embeddingModels[0]?.id || 0,
      chunk_size: 500,
      chunk_overlap: 50,
      description: '',
    });
  };

  const openDeleteModal = (knowledge: Knowledge) => {
    setSelectedKnowledge(knowledge);
    setShowDeleteModal(true);
  };

  if (loading) {
    return <PageLoading />;
  }

  return (
    <div className="container mx-auto px-4 py-6">
      {/* 页面标题和操作 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">知识库管理</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">管理和配置知识库</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          新建知识库
        </Button>
      </div>

      {/* 搜索栏 */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 max-w-md">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索知识库..."
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

      {/* 知识库列表 */}
      {knowledges.length === 0 ? (
        <EmptyState
          icon={<Database className="h-12 w-12" />}
          title="暂无知识库"
          description="创建第一个知识库开始使用"
          action={
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              新建知识库
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {knowledges.map((knowledge) => (
            <Card key={knowledge.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-center">
                    <div className="h-10 w-10 rounded-lg bg-primary-100 dark:bg-primary-900 flex items-center justify-center">
                      <Database className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div className="ml-3">
                      <h3 className="font-medium text-gray-900 dark:text-white">{knowledge.name}</h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {knowledge.document_count} 文档 · {knowledge.total_chunks} 切片
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => window.location.href = `/knowledge/${knowledge.id}`}
                      className="p-1.5 text-gray-400 hover:text-primary-600 transition-colors"
                      title="管理文档"
                    >
                      <FileText className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => openDeleteModal(knowledge)}
                      className="p-1.5 text-gray-400 hover:text-red-600 transition-colors"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                
                {knowledge.description && (
                  <p className="mt-3 text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {knowledge.description}
                  </p>
                )}
                
                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                    <span>切片大小: {knowledge.chunk_size}</span>
                    <span>创建于: {formatDateTime(knowledge.created_at)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* 创建知识库弹窗 */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="新建知识库"
        size="md"
      >
        <div className="space-y-4">
          <Input
            label="知识库名称"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="请输入知识库名称"
          />
          
          <Select
            label="Embedding模型"
            value={formData.embed_llm_id}
            onChange={(e) => setFormData({ ...formData, embed_llm_id: parseInt(e.target.value) })}
            options={embeddingModels.map(m => ({ value: m.id, label: m.name }))}
          />
          
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="切片大小"
              type="number"
              value={formData.chunk_size}
              onChange={(e) => setFormData({ ...formData, chunk_size: parseInt(e.target.value) || 500 })}
              helperText="建议 300-1000"
            />
            <Input
              label="重叠大小"
              type="number"
              value={formData.chunk_overlap}
              onChange={(e) => setFormData({ ...formData, chunk_overlap: parseInt(e.target.value) || 50 })}
              helperText="建议 30-100"
            />
          </div>
          
          <Textarea
            label="描述（可选）"
            value={formData.description || ''}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="请输入知识库描述"
            rows={3}
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

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        title="删除知识库"
        message={`确定要删除知识库"${selectedKnowledge?.name}"吗？此操作将同时删除所有关联的文档和向量数据，且不可恢复。`}
        confirmText="删除"
        variant="danger"
        loading={formLoading}
      />
    </div>
  );
}
