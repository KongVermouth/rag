'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import 'katex/dist/katex.min.css';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Upload, FileText, Trash2, RefreshCw, Check, X, Clock, AlertCircle, Filter, ChevronDown, ChevronUp, Eye, Maximize2, Settings, Download, FileSpreadsheet, Presentation } from 'lucide-react';
import toast from 'react-hot-toast';
import * as XLSX from 'xlsx';
import { renderAsync } from 'docx-preview';
import { Button, Switch } from '@/components/ui';
import { PageLoading, EmptyState } from '@/components/ui/loading';
import { Modal, ConfirmModal } from '@/components/ui/modal';
import { Select } from '@/components/ui/form';
import { formatFileSize, formatDateTime, getDocumentStatusInfo } from '@/lib/utils';
import { knowledgeApi, documentApi, healthApi } from '@/api';
import apiClient, { ApiError } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';
import { useDocumentStore } from '@/stores/document-store';
import type { Knowledge, Document, DocumentUploadResponse } from '@/types';

export default function KnowledgeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const knowledgeIdStr = params.id as string;
  const knowledgeId = parseInt(knowledgeIdStr);
  console.log(`DEBUG: KnowledgeDetailPage rendering for ID: ${knowledgeIdStr} (parsed: ${knowledgeId})`);
  const { isAuthenticated, isLoading: authLoading, token: authStoreToken } = useAuthStore();
  const { addFailedUpload, removeFailedUpload, failedUploads } = useDocumentStore();

  const [knowledge, setKnowledge] = useState<Knowledge | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [expandedErrors, setExpandedErrors] = useState<Record<number, boolean>>({});
  const [retryingDocs, setRetryingDocs] = useState<Record<number, boolean>>({});
  
  // 上传配置
  const [autoPreview, setAutoPreview] = useState(true);
  const [showUploadSettings, setShowUploadSettings] = useState(false);
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [loadingMarkdown, setLoadingMarkdown] = useState(false);
  const [excelData, setExcelData] = useState<any[][] | null>(null);
  const [docxBlob, setDocxBlob] = useState<Blob | null>(null);
  const docxContainerRef = useRef<HTMLDivElement>(null);

  // 加载文本/Markdown 内容
  const fetchTextContent = async (docId: number) => {
    setLoadingMarkdown(true);
    try {
      // 修正 API URL，apiClient 已包含 /api/v1
      const response = await apiClient.get(`/documents/${docId}/preview`, {
        responseType: 'text'
      });
      setMarkdownContent(typeof response.data === 'string' ? response.data : JSON.stringify(response.data, null, 2));
    } catch (error: any) {
      console.error(`加载文档内容失败 [ID: ${docId}]:`, error);
      const detail = error instanceof ApiError ? error.message : error.message;
      toast.error(`加载文档内容失败: ${detail}`);
    } finally {
      setLoadingMarkdown(false);
    }
  };

  // 加载 Office 内容
  const fetchOfficeContent = async (doc: Document) => {
    setLoadingMarkdown(true);
    try {
      const response = await apiClient.get(`/documents/${doc.id}/preview`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: doc.mime_type });

      if (doc.file_extension === 'xlsx') {
        const reader = new FileReader();
        reader.onload = (e) => {
          const data = new Uint8Array(e.target?.result as ArrayBuffer);
          const workbook = XLSX.read(data, { type: 'array' });
          const firstSheetName = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[firstSheetName];
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
          setExcelData(jsonData as any[][]);
        };
        reader.readAsArrayBuffer(blob);
      } else if (doc.file_extension === 'docx') {
        setDocxBlob(blob);
      }
    } catch (error: any) {
      console.error(`加载 Office 文档失败 [ID: ${doc.id}, MIME: ${doc.mime_type}]:`, error);
      toast.error('解析文档失败，请尝试下载后查看');
    } finally {
      setLoadingMarkdown(false);
    }
  };

  useEffect(() => {
    if (showPreviewModal && selectedDoc) {
      const ext = selectedDoc.file_extension.toLowerCase();
      if (ext === 'md' || ext === 'txt') {
        fetchTextContent(selectedDoc.id);
      } else if (ext === 'docx' || ext === 'xlsx') {
        fetchOfficeContent(selectedDoc);
      }
    } else {
      setMarkdownContent('');
      setExcelData(null);
      setDocxBlob(null);
    }
  }, [showPreviewModal, selectedDoc]);

  // 处理 docx 渲染
  useEffect(() => {
    if (docxBlob && docxContainerRef.current) {
      renderAsync(docxBlob, docxContainerRef.current)
        .catch(err => {
          console.error('docx-preview 渲染失败:', err);
          toast.error('文档渲染失败');
        });
    }
  }, [docxBlob]);

  // 分页状态
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);

  // API 基础路径，用于直接展示图片/PDF
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  // 获取带 token 的预览 URL
  const getPreviewUrl = (docId: number, type: 'preview' | 'thumb' = 'preview') => {
    const baseUrl = `${API_URL}/api/v1/documents/${docId}/${type}`;
    return authStoreToken ? `${baseUrl}?token=${authStoreToken}` : baseUrl;
  };

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
  const loadData = useCallback(async (retryCount = 0, silent = false) => {
    if (authLoading) return;
    
    // 只有在非静默加载且是第一次加载时才显示全屏 loading
    if (retryCount === 0 && !silent && !dataLoadedRef.current) {
      setLoading(true);
    }

    try {
      const [kb, docs] = await Promise.all([
        knowledgeApi.getById(knowledgeId),
        documentApi.getList({
          knowledge_id: knowledgeId,
          skip: (page - 1) * pageSize,
          limit: pageSize,
          status_filter: statusFilterRef.current || undefined
        }),
      ]);
      
      if (!kb) throw new Error('获取知识库详情失败');
      if (!docs || !Array.isArray(docs.items)) throw new Error('获取文档列表格式错误');

      setKnowledge(kb);
      setDocuments(docs.items);
      setTotal(docs.total || 0);
      dataLoadedRef.current = true;
    } catch (error: any) {
      console.error(`加载数据失败 (重试 ${retryCount}/3):`, error);
      
      // 1. 详细日志记录
      if (error instanceof ApiError) {
        console.log('DEBUG: ApiError Details:', {
          status: error.status,
          message: error.message,
          data: error.data
        });
        
        const status = error.status;
        if (status === 401) {
          router.push('/auth/login');
          return;
        }
        if (status === 403) {
          toast.error('权限不足，无法访问此知识库');
          router.push('/knowledge');
          return;
        }
        if (status === 404) {
          toast.error(error.message || '知识库或文档不存在');
          router.push('/knowledge');
          return;
        }
      } else if (error instanceof Error) {
        console.log('DEBUG: Standard Error Details:', {
          message: error.message,
          stack: error.stack
        });
        
        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
          router.push('/auth/login');
          return;
        }
      }

      // 2. 重试逻辑
      if (retryCount < 3) {
        const delay = Math.pow(2, retryCount) * 1000;
        setTimeout(() => loadData(retryCount + 1), delay);
        return; // 重要：重试时不关闭 loading
      } else {
        toast.error(error instanceof Error ? `加载数据失败: ${error.message}` : '加载数据失败，请检查网络后重试');
      }
    } finally {
      // 只有在非重试的情况下，或者达到最大重试次数时，才关闭 loading
      if (retryCount === 0 || retryCount === 3) {
        setLoading(false);
      }
    }
  }, [knowledgeId, authLoading, router, page, pageSize]);

  // 初始加载
  useEffect(() => {
    if (isNaN(knowledgeId)) {
      toast.error('无效的知识库ID');
      router.push('/knowledge');
      return;
    }

    if (!authLoading && !dataLoadedRef.current) {
      loadData();
    }
  }, [authLoading, loadData, knowledgeId, router]);

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
            if (status.status === 'failed') {
              addFailedUpload({
                id: doc.id,
                fileName: doc.file_name,
                errorMsg: status.error_msg || '未知错误',
                knowledgeId: knowledgeId,
                timestamp: Date.now()
              });
            } else if (status.status === 'completed') {
              removeFailedUpload(doc.id);
            }
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

  // 合并本地失败记录和后端文档列表
  const allDocuments = [
    ...documents,
    ...failedUploads
      .filter(fu => {
        // 1. 必须是当前知识库的
        if (fu.knowledgeId !== knowledgeId) return false;
        
        // 2. 如果 documents 中已经存在该 ID 或同名文件且状态不是失败，则不显示本地错误记录
        const duplicate = documents.find(d => 
          d.id === fu.id || 
          (d.file_name === fu.fileName && d.status !== 'failed')
        );
        return !duplicate;
      })
      .map(fu => ({
        id: fu.id,
        file_name: fu.fileName,
        file_size: 0,
        status: 'failed' as const,
        chunk_count: 0,
        error_msg: fu.errorMsg,
        created_at: new Date(fu.timestamp).toISOString(),
        knowledge_id: fu.knowledgeId,
        file_extension: fu.fileName.split('.').pop() || '',
        file_path: ''
      }))
  ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    
    // 1. 上传前预检：校验后端分词器可用性
    let isAnalyzerHealthy = true;
    const healthToastId = 'analyzer-health-check';
    try {
      await healthApi.checkES();
    } catch (error: any) {
      console.error('上传预检失败:', error);
      isAnalyzerHealthy = false;
      let errorMsg = '后端分词器配置错误';
      
      if (error instanceof ApiError) {
        if (error.data?.error_type === 'illegal_argument_exception') {
          errorMsg = '后端分词器配置错误(IK)';
        } else if (error.status === 503) {
          errorMsg = '搜索引擎服务不可用(IK分词器缺失)';
        }
      }
      
      // 使用 loading 类型的 toast 提示预检警告，避免红色的 error 提示带来“上传失败”的错觉
      toast.loading(`${errorMsg}。系统将尝试进入降级模式上传...`, { 
        id: healthToastId,
      });
    }

    let successCount = 0;
    let failCount = 0;

    for (const file of Array.from(files)) {
      const uploadWithRetry = async (retryCount = 0): Promise<DocumentUploadResponse> => {
        try {
          const startTime = Date.now();
          const response = await documentApi.upload(knowledgeId, file);
          const duration = Date.now() - startTime;
          console.log(`DEBUG: Upload successful for ${file.name}, Duration: ${duration}ms, Retry: ${retryCount}`);
          
          return response;
        } catch (error: any) {
          // 如果预检已经失败，且当前是分词器相关错误，则不再重试，直接抛出
          if (!isAnalyzerHealthy && error instanceof ApiError && error.data?.error_type === 'illegal_argument_exception') {
            throw error;
          }

          if (retryCount < 2) {
            console.warn(`DEBUG: Upload failed for ${file.name}, retrying ${retryCount + 1}/2...`);
            await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1)));
            return uploadWithRetry(retryCount + 1);
          }
          throw error;
        }
      };

      try {
        const response = await uploadWithRetry();
        successCount++;
        
        // 只有在开启了自动预览且只有一个文件时才自动打开预览
        if (autoPreview && files.length === 1 && response.preview_url) {
           const previewDoc: Document = {
             id: response.document_id,
             knowledge_id: knowledgeId,
             file_name: response.filename,
             file_extension: response.filename.split('.').pop() || '',
             file_size: response.file_size,
             mime_type: response.mime_type,
             preview_url: response.preview_url,
             status: 'uploading',
             chunk_count: 0,
             created_at: new Date().toISOString(),
             updated_at: new Date().toISOString(),
             file_path: ''
           };
           setSelectedDoc(previewDoc);
           setShowPreviewModal(true);
        }
      } catch (error: any) {
        failCount++;
        let message = error instanceof Error ? error.message : '上传失败';
        
        if (error instanceof ApiError && error.data?.error_type === 'illegal_argument_exception') {
          message = '分词器配置错误，已触发自动降级存储';
        }
        
        toast.error(`${file.name}: ${message}`);
        addFailedUpload({
          id: -Date.now(),
          fileName: file.name,
          errorMsg: message,
          knowledgeId: knowledgeId,
          timestamp: Date.now()
        });
      }
    }

    // 上传完成后统一关闭预检警告
    if (!isAnalyzerHealthy) {
      toast.dismiss(healthToastId);
    }

    if (successCount > 0) {
      toast.success(`成功上传 ${successCount} 个文件`);
      // 使用静默更新，避免全屏 loading 闪烁
      loadData(0, true);
    }

    setUploading(false);
    e.target.value = '';
  };

  const handleDelete = async () => {
    if (!selectedDoc) return;

    setDeleteLoading(true);
    try {
      if (selectedDoc.id > 0) {
        await documentApi.delete(selectedDoc.id);
      }
      removeFailedUpload(selectedDoc.id);
      toast.success('文档删除成功');
      setShowDeleteModal(false);
      setSelectedDoc(null);
      loadData();
    } catch (error) {
      const message = error instanceof Error ? error.message : '删除失败';
      toast.error(message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleRetry = async (doc: Document) => {
    setRetryingDocs(prev => ({ ...prev, [doc.id]: true }));
    try {
      const response = await documentApi.retry(doc.id);
      if (response.code === 200) {
        toast.success('重试任务已启动');
        removeFailedUpload(doc.id);
        loadData();
      } else {
        toast.error(response.message);
      }
    } catch (error) {
      toast.error('重试启动失败');
    } finally {
      setRetryingDocs(prev => ({ ...prev, [doc.id]: false }));
    }
  };

  const toggleError = (id: number) => {
    setExpandedErrors(prev => ({ ...prev, [id]: !prev[id] }));
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
          <Button variant="outline" size="sm" onClick={() => setShowUploadSettings(!showUploadSettings)} title="上传设置">
            <Settings className={`h-4 w-4 ${showUploadSettings ? 'text-blue-600' : ''}`} />
          </Button>
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

      {/* 上传设置面板 */}
      {showUploadSettings && (
        <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700 animate-in fade-in slide-in-from-top-2">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">上传配置</h3>
          <div className="flex flex-wrap gap-6">
            <Switch
              label="上传成功后自动打开预览"
              checked={autoPreview}
              onChange={(e) => setAutoPreview(e.target.checked)}
            />
          </div>
        </div>
      )}

      {/* 文档列表 */}
      {allDocuments.length === 0 ? (
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
              {allDocuments.map((doc) => {
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
                        <div className="mt-1">
                          <button
                            onClick={() => toggleError(doc.id)}
                            className="flex items-center text-xs text-red-500 hover:text-red-700"
                          >
                            <span>向量化失败</span>
                            {expandedErrors[doc.id] ? (
                              <ChevronUp className="ml-1 h-3 w-3" />
                            ) : (
                              <ChevronDown className="ml-1 h-3 w-3" />
                            )}
                          </button>
                          {expandedErrors[doc.id] && (
                            <div className="mt-1 p-2 bg-red-50 dark:bg-red-900/20 rounded text-[10px] text-red-600 dark:text-red-400 break-all whitespace-pre-wrap max-w-xs border border-red-100 dark:border-red-800">
                              {doc.error_msg}
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {doc.chunk_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                      {formatDateTime(doc.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex justify-end items-center space-x-3">
                        <button
                          onClick={() => {
                            setSelectedDoc(doc);
                            setShowPreviewModal(true);
                          }}
                          className="text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                          title="预览"
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                        {doc.status === 'failed' && (
                          <button
                            onClick={() => handleRetry(doc)}
                            disabled={retryingDocs[doc.id]}
                            className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 transition-colors flex items-center"
                            title="重试"
                          >
                            <RefreshCw className={`h-4 w-4 ${retryingDocs[doc.id] ? 'animate-spin' : ''}`} />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setSelectedDoc(doc);
                            setShowDeleteModal(true);
                          }}
                          className="text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* 分页组件 */}
          {total > 0 && (
            <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <div className="text-sm text-gray-500 dark:text-gray-400">
                共 {total} 个文档，每页显示 {pageSize} 条
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  上一页
                </Button>
                <div className="text-sm font-medium text-gray-900 dark:text-white px-2">
                  第 {page} / {Math.ceil(total / pageSize)} 页
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= Math.ceil(total / pageSize)}
                  onClick={() => setPage(page + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 删除确认弹窗 */}
      <ConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        title="删除文档"
        message={`确定要删除文档"${selectedDoc?.file_name}"吗？此操作将同时删除关联的向量数据，且不可恢复。`}
        confirmText="删除"
        variant="danger"
        loading={deleteLoading}
      />

      {/* 预览弹窗 */}
      <Modal
        isOpen={showPreviewModal}
        onClose={() => setShowPreviewModal(false)}
        title={`预览: ${selectedDoc?.file_name}`}
        size="xl"
      >
        <div className="flex flex-col h-[70vh]">
          <div className="flex-1 bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden flex items-center justify-center relative">
            {selectedDoc && (
              <>
                {/* 图片预览 */}
                {selectedDoc.mime_type?.startsWith('image/') && (
                  <img
                    src={getPreviewUrl(selectedDoc.id, 'preview')}
                    alt={selectedDoc.file_name}
                    className="max-w-full max-h-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = getPreviewUrl(selectedDoc.id, 'thumb');
                    }}
                  />
                )}

                {/* PDF 预览 */}
                {selectedDoc.mime_type === 'application/pdf' && (
                  <iframe
                    src={`${getPreviewUrl(selectedDoc.id, 'preview')}#toolbar=0`}
                    className="w-full h-full border-none"
                    title="PDF Preview"
                  />
                )}

                {/* 视频预览 */}
                {selectedDoc.mime_type?.startsWith('video/') && (
                  <video controls className="max-w-full max-h-full">
                    <source src={getPreviewUrl(selectedDoc.id, 'preview')} type={selectedDoc.mime_type} />
                    您的浏览器不支持视频播放
                  </video>
                )}

                {/* Office 文档预览 */}
                {selectedDoc.file_extension === 'docx' && (
                  <div className="w-full h-full bg-white dark:bg-gray-800 p-4 overflow-auto custom-scrollbar">
                    {loadingMarkdown ? (
                      <div className="flex flex-col items-center justify-center h-full">
                        <RefreshCw className="h-8 w-8 animate-spin text-blue-500 mb-2" />
                        <p className="text-sm text-gray-500">正在解析 Word 文档...</p>
                      </div>
                    ) : (
                      <div ref={docxContainerRef} className="docx-preview-container" />
                    )}
                  </div>
                )}

                {selectedDoc.file_extension === 'xlsx' && (
                  <div className="w-full h-full bg-white dark:bg-gray-800 p-0 overflow-auto custom-scrollbar">
                    {loadingMarkdown ? (
                      <div className="flex flex-col items-center justify-center h-full">
                        <RefreshCw className="h-8 w-8 animate-spin text-blue-500 mb-2" />
                        <p className="text-sm text-gray-500">正在解析 Excel 表格...</p>
                      </div>
                    ) : (
                      <div className="overflow-auto max-h-full">
                        <table className="min-w-full border-collapse">
                          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                            {excelData?.map((row, rowIndex) => (
                              <tr key={rowIndex} className={rowIndex === 0 ? 'bg-gray-50 dark:bg-gray-900 font-bold' : ''}>
                                {row.map((cell, cellIndex) => (
                                  <td key={cellIndex} className="px-4 py-2 border border-gray-200 dark:border-gray-700 text-sm whitespace-nowrap">
                                    {cell?.toString() || ''}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {selectedDoc.file_extension === 'pptx' && (
                  <div className="flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-gray-800 w-full h-full">
                    <Presentation className="h-16 w-16 text-orange-500 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">PowerPoint 演示文稿</h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-6">PPTX 格式暂不支持直接在线预览，建议下载后使用本地软件查看</p>
                    <div className="flex space-x-4">
                      <Button onClick={() => window.open(getPreviewUrl(selectedDoc.id, 'preview'), '_blank')}>
                        <Download className="h-4 w-4 mr-2" />
                        下载文档
                      </Button>
                    </div>
                  </div>
                )}

                {/* 文本/Markdown 预览 */}
                {(selectedDoc.file_extension === 'txt' || selectedDoc.file_extension === 'md') && (
                  <div className="w-full h-full bg-white dark:bg-gray-800 p-6 overflow-auto custom-scrollbar prose dark:prose-invert max-w-none">
                    {loadingMarkdown ? (
                      <div className="flex flex-col items-center justify-center h-full">
                        <RefreshCw className="h-8 w-8 animate-spin text-blue-500 mb-2" />
                        <p className="text-sm text-gray-500">正在解析内容...</p>
                      </div>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[rehypeKatex, rehypeRaw]}
                        components={{
                          code({ node, className, children, ...props }: any) {
                            const match = /language-(\w+)/.exec(className || '');
                            const isInline = !match && !node?.position?.start.line;
                            return !isInline && match ? (
                              <SyntaxHighlighter
                                style={vscDarkPlus}
                                language={match[1]}
                                PreTag="div"
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            );
                          },
                          img({ node, src, ...props }: any) {
                            // 处理相对路径图片
                            let fullSrc = src;
                            if (src && !src.startsWith('http') && !src.startsWith('data:')) {
                              // 如果是相对路径，尝试拼接后端地址
                              // 注意：这里的逻辑可能需要根据后端实际存储结构调整
                              fullSrc = src.startsWith('/') ? `${API_URL}${src}` : `${API_URL}/${src}`;
                            }
                            return (
                              <div className="my-4 flex justify-center">
                                <img 
                                  {...props} 
                                  src={fullSrc}
                                  className="max-w-full rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300" 
                                  loading="lazy" 
                                />
                              </div>
                            );
                          },
                          a({ node, href, children, ...props }: any) {
                            // 识别图片链接并美化
                            const isImageLink = typeof children === 'string' && (children.endsWith('.png') || children.endsWith('.jpg') || children.endsWith('.jpeg') || children.endsWith('.gif'));
                            return (
                              <a 
                                {...props} 
                                href={href}
                                className="text-blue-600 hover:text-blue-800 underline decoration-blue-300 hover:decoration-blue-600 transition-all" 
                                target="_blank" 
                                rel="noopener noreferrer"
                              >
                                {children}
                              </a>
                            );
                          },
                          table({ children }: any) {
                            return (
                              <div className="overflow-x-auto my-6 rounded-lg border border-gray-200 dark:border-gray-700">
                                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 m-0">
                                  {children}
                                </table>
                              </div>
                            );
                          },
                          th({ children }: any) {
                            return <th className="px-4 py-2 bg-gray-50 dark:bg-gray-900 text-left text-xs font-semibold uppercase tracking-wider">{children}</th>;
                          },
                          td({ children }: any) {
                            return <td className="px-4 py-2 text-sm border-t border-gray-100 dark:border-gray-800">{children}</td>;
                          }
                        }}
                      >
                        {markdownContent}
                      </ReactMarkdown>
                    )}
                  </div>
                )}

                {/* 不支持的类型 */}
                {!selectedDoc.mime_type?.startsWith('image/') && 
                 selectedDoc.mime_type !== 'application/pdf' && 
                 !selectedDoc.mime_type?.startsWith('video/') && 
                 !['docx', 'xlsx', 'pptx', 'txt', 'md'].includes(selectedDoc.file_extension.toLowerCase()) && (
                  <div className="flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-gray-800 w-full h-full">
                    <AlertCircle className="h-16 w-16 text-yellow-500 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">暂不支持预览</h3>
                    <p className="text-gray-600 dark:text-gray-400 mb-6">
                      该文件格式 ({selectedDoc.file_extension}) 暂不支持在线预览，请下载后查看。
                    </p>
                    <Button 
                      onClick={() => window.open(getPreviewUrl(selectedDoc.id, 'preview'), '_blank')}
                    >
                      <Download className="h-4 w-4 mr-2" />
                      下载文件
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
          
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              {selectedDoc?.mime_type} | {formatFileSize(selectedDoc?.file_size || 0)}
            </div>
            <div className="flex space-x-3">
              <Button 
                variant="outline" 
                onClick={() => window.open(getPreviewUrl(selectedDoc?.id || 0, 'preview'), '_blank')}
              >
                <Maximize2 className="h-4 w-4 mr-2" />
                全屏查看
              </Button>
              <Button 
                variant="secondary"
                onClick={() => {
                  setShowPreviewModal(false);
                  setSelectedDoc(selectedDoc);
                  setShowDeleteModal(true);
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                删除
              </Button>
              <Button onClick={() => setShowPreviewModal(false)}>
                关闭
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
