'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Upload, FileText, Trash2, RefreshCw, Check, X, Clock, AlertCircle, Filter } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui';
import { PageLoading, EmptyState } from '@/components/ui/loading';
import { ConfirmModal } from '@/components/ui/modal';
import { Select } from '@/components/ui/form';
import { formatFileSize, formatDateTime, getDocumentStatusInfo } from '@/lib/utils';
import { knowledgeApi, documentApi } from '@/api';
import { useAuthStore } from '@/stores/auth-store';
import type { Knowledge, Document } from '@/types';

export default function KnowledgeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const knowledgeId = parseInt(params.id as string);
  const { isAuthenticated, isLoading: authLoading } = useAuthStore();

  const [knowledge, setKnowledge] = useState<Knowledge | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showDeleteModal, setDeleteModal] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');

  // 使用 ref 跟踪是否已加载数据，避免重复加载
  const dataLoadedRef = useRef(false);
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);
  // 使用 ref 保存最新的 statusFilter，避免闭包问题
  const statusFilterRef = useRef('');

  // 更新 ref 当 statusFilter 变化时
  useEffect(() => {
    statusFilterRef.current = statusFilter;
  }, [statusFilter]);

  // 加载数据
  const loadData = useCallback(async () => {
    if (authLoading) return;

    try {
      const [kb, docs] = await Promise.all([
        knowledgeApi.getById(knowledgeId),
        documentApi.getList({
          knowledge_id: knowledgeId,
          limit: 100,
          status_filter: statusFilterRef.current || undefined
        }),
      ]);
      setKnowledge(kb);
      setDocuments(docs.items);
      dataLoadedRef.current = true;
    } catch (error) {
      if (error instanceof Error && (error.message.includes('401') || error.message.includes('Unauthorized'))) {
        router.push('/auth/login');
        return;
      }
      toast.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  }, [knowledgeId, authLoading, router]);

  // 初始加载
  useEffect(() => {
    if (!authLoading && !dataLoadedRef.current) {
      loadData();
    }
  }, [authLoading, loadData]);

  // 轮询检查处理中的文档状态
  useEffect(() => {
    const processingDocs = documents.filter(d =>
      ['uploading', 'parsing', 'embedding'].includes(d.status)
    );

    if (processingDocs.length > 0) {
      pollingTimerRef.current = setInterval(async () => {
        for (const doc of processingDocs) {
          try {
            const status = await documentApi.getStatus(doc.id);
            setDocuments(prev => prev.map(d => {
              if (d.id === doc.id) {
                const validStatus = ['uploading', 'parsing', 'embedding', 'completed', 'failed'].includes(status.status)
                  ? status.status as 'uploading' | 'parsing' | 'embedding' | 'completed' | 'failed'
                  : d.status;

                return {
                  ...d,
                  status: validStatus,
                  chunk_count: status.chunk_count,
                  error_msg: status.error_msg
                };
              }
              return d;
            }));
          } catch (error) {
            console.error('获取文档状态失败', error);
          }
        }
      }, 3000);

      return () => {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current);
        }
      };
    }
  }, [documents]);

  // 清理轮询定时器
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, []);

  // 未认证或加载中时显示加载状态
  if (authLoading || loading) {
    return <PageLoading />;
  }

  // 未认证时返回null（由MainLayout处理跳转）
  if (!isAuthenticated) {
    return null;
  }

  // 知识库不存在
  if (!knowledge) {
    return (
      <div className="container mx-auto px-4 py-6">
        <EmptyState
          icon={<AlertCircle className="h-12 w-12" />}
          title="知识库不存在"
          action={<Button onClick={() => router.push('/knowledge')}>返回列表</Button>}
        />
      </div>
    );
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    let successCount = 0;
    let failCount = 0;

    for (const file of Array.from(files)) {
      try {
        await documentApi.upload(knowledgeId, file);
        successCount++;
      } catch (error) {
        failCount++;
        const message = error instanceof Error ? error.message : '上传失败';
        toast.error(`${file.name}: ${message}`);
      }
    }

    if (successCount > 0) {
      toast.success(`成功上传 ${successCount} 个文件`);
      loadData();
    }

    setUploading(false);
    e.target.value = '';
  };

  const handleDelete = async () => {
    if (!selectedDoc) return;

    setDeleteLoading(true);
    try {
      await documentApi.delete(selectedDoc.id);
      toast.success('文档删除成功');
      setDeleteModal(false);
      setSelectedDoc(null);
      loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      toast.error(message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setLoading(true);
    loadData();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <Check className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <X className="h-4 w-4 text-red-500" />;
      case 'uploading':
      case 'parsing':
      case 'embedding':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  return (
    <div className="container mx-auto px-4 py-6">
      {/* 返回按钮和标题 */}
      <div className="flex items-center mb-6">
        <button
          onClick={() => router.push('/knowledge')}
          className="mr-4 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5 text-gray-600 dark:text-gray-400" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{knowledge.name}</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            {knowledge.document_count} 个文档 · {knowledge.total_chunks} 个切片
          </p>
        </div>
      </div>

      {/* 状态筛选和操作栏 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <Select
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="w-40"
            >
              <option value="">全部状态</option>
              <option value="uploading">上传中</option>
              <option value="parsing">解析中</option>
              <option value="embedding">向量化中</option>
              <option value="completed">已完成</option>
              <option value="failed">失败</option>
            </Select>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            刷新
          </Button>
          <Button loading={uploading} disabled={uploading}>
            <label className="cursor-pointer flex items-center">
              <Upload className="h-4 w-4 mr-2" />
              上传文档
              <input
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.txt,.md,.html"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </Button>
        </div>
      </div>

      {/* 文档列表 */}
      {documents.length === 0 ? (
        <EmptyState
          icon={<FileText className="h-12 w-12" />}
          title="暂无文档"
          description="上传文档开始构建知识库"
          action={
            <Button loading={uploading} disabled={uploading}>
              <label className="cursor-pointer flex items-center">
                <Upload className="h-4 w-4 mr-2" />
                上传文档
                <input
                  type="file"
                  multiple
                  accept=".pdf,.doc,.docx,.txt,.md,.html"
                  className="hidden"
                  onChange={handleUpload}
                  disabled={uploading}
                />
              </label>
            </Button>
          }
        />
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  文件名
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  大小
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  切片数
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  上传时间
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {documents.map((doc) => {
                const statusInfo = getDocumentStatusInfo(doc.status);
                return (
                  <tr key={doc.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <FileText className="h-5 w-5 text-gray-400 mr-2" />
                        <span className="text-sm text-gray-900 dark:text-white">{doc.file_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        {getStatusIcon(doc.status)}
                        <span className={`ml-2 text-sm ${statusInfo.color}`}>
                          {statusInfo.text}
                        </span>
                      </div>
                      {doc.error_msg && (
                        <p className="text-xs text-red-500 mt-1">{doc.error_msg}</p>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {doc.chunk_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDateTime(doc.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <button
                        onClick={() => {
                          setSelectedDoc(doc);
                          setShowDeleteModal(true);
                        }}
                        className="text-gray-400 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setDeleteModal(false)}
        onConfirm={handleDelete}
        title="删除文档"
        message={`确定要删除文档"${selectedDoc?.file_name}"吗？此操作将同时删除关联的向量数据，且不可恢复。`}
        confirmText="删除"
        variant="danger"
        loading={deleteLoading}
      />
    </div>
  );
}
