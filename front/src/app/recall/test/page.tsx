'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, 
  RotateCcw, 
  Download, 
  Upload, 
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Info,
  ChevronRight,
  ChevronLeft,
  Search as SearchIcon,
  ExternalLink,
  Settings2
} from 'lucide-react';
import { 
  Button, 
  Card, 
  CardHeader, 
  CardTitle, 
  CardContent, 
  Input, 
  Textarea, 
  Loading,
  Modal,
  Select
} from '@/components/ui';
import { cn } from '@/lib/utils';
import { recallApi, knowledgeApi, robotApi } from '@/api';
import type { 
  RecallTestQuery, 
  RecallTestResultItem, 
  RecallTestStatusResponse,
  Knowledge,
  Robot
} from '@/types';
import { toast } from 'react-hot-toast';

export default function RecallTestPage() {
  // 状态管理
  const [queriesText, setQueriesText] = useState('');
  const [topN, setTopN] = useState(10);
  const [threshold, setThreshold] = useState(0.7);
  const [selectedKnowledgeIds, setSelectedKnowledgeIds] = useState<number[]>([]);
  const [selectedRobotId, setSelectedRobotId] = useState<number | undefined>(undefined);
  
  const [knowledges, setKnowledges] = useState<Knowledge[]>([]);
  const [robots, setRobots] = useState<Robot[]>([]);
  
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<RecallTestStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // 过滤与分页
  const [searchTerm, setSearchTerm] = useState('');
  const [pageSize, setPageSize] = useState(50);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortField, setSortField] = useState<keyof RecallTestResultItem>('query');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  
  // 详情弹窗
  const [detailItem, setDetailItem] = useState<RecallTestResultItem | null>(null);

  // 轮询定时器
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // 初始化加载
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [kbRes, robotRes] = await Promise.all([
          knowledgeApi.getList({ limit: 100 }),
          robotApi.getList({ limit: 100 })
        ]);
        setKnowledges(kbRes.items);
        setRobots(robotRes.items);
      } catch (error) {
        toast.error('获取初始化数据失败');
      }
    };
    fetchData();
  }, []);

  // 校验逻辑
  const validateInputs = () => {
    if (!queriesText.trim()) {
      toast.error('请输入提问词');
      return false;
    }
    if (selectedKnowledgeIds.length === 0) {
      toast.error('请选择至少一个知识库');
      return false;
    }
    if (queriesText.length > 20000) {
      toast.error('提问词内容过长，超过20000字符限制');
      return false;
    }
    return true;
  };

  // 停止轮询
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // 轮询状态
  const pollStatus = useCallback(async (tid: string) => {
    try {
      const res = await recallApi.getStatus(tid);
      setStatus(res);
      
      if (res.status === 'finished' || res.status === 'failed') {
        stopPolling();
        setIsProcessing(false);
        if (res.status === 'finished') {
          toast.success('测试完成');
        } else {
          toast.error(res.error || '测试任务失败');
        }
      }
    } catch (error) {
      console.error('获取状态失败', error);
      // 偶尔一次失败不停止轮询，除非连续失败
    }
  }, [stopPolling]);

  // 开始测试
  const handleRun = async () => {
    if (!validateInputs()) return;
    
    setLoading(true);
    try {
      const queries: RecallTestQuery[] = queriesText
        .split('\n')
        .filter(q => q.trim())
        .map(q => ({ query: q.trim() }));
        
      if (queries.length > 5000) {
        toast.error('单次最多支持5000条提问词');
        return;
      }

      const res = await recallApi.startTest({
        queries,
        topN,
        threshold,
        knowledge_ids: selectedKnowledgeIds,
        robot_id: selectedRobotId
      });
      
      setTaskId(res.taskId);
      setIsProcessing(true);
      setCurrentPage(1);
      
      // 开始轮询
      pollingRef.current = setInterval(() => pollStatus(res.taskId), 2000);
      
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '启动测试失败');
    } finally {
      setLoading(false);
    }
  };

  // 重置
  const handleReset = () => {
    if (isProcessing) return;
    setQueriesText('');
    setTaskId(null);
    setStatus(null);
    stopPolling();
  };

  // 文件导入
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      toast.error('文件大小不能超过10MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setQueriesText(content);
      toast.success('文件导入成功');
    };
    reader.onerror = () => toast.error('读取文件失败');
    reader.readAsText(file);
    
    // 清除 input 值，以便下次可以选择同一文件
    e.target.value = '';
  };

  // CSV 导出
  const handleExport = () => {
    if (!status?.results || status.results.length === 0) return;
    
    const headers = ['Query', 'Recall', 'Precision', 'F1', 'Top-N Hit', 'Latency(s)'];
    const rows = status.results.map(r => [
      r.query,
      r.recall.toFixed(4),
      r.precision.toFixed(4),
      r.f1.toFixed(4),
      r.top_n_hit ? 'Yes' : 'No',
      r.latency.toFixed(4)
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');
    
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `recall_test_results_${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 排序与过滤逻辑
  const sortedAndFilteredResults = status?.results?.filter(r => 
    r.query.toLowerCase().includes(searchTerm.toLowerCase())
  ).sort((a, b) => {
    const valA = a[sortField];
    const valB = b[sortField];
    if (typeof valA === 'number' && typeof valB === 'number') {
      return sortOrder === 'asc' ? valA - valB : valB - valA;
    }
    return sortOrder === 'asc' 
      ? String(valA).localeCompare(String(valB)) 
      : String(valB).localeCompare(String(valA));
  }) || [];

  const paginatedResults = sortedAndFilteredResults.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  const totalPages = Math.ceil(sortedAndFilteredResults.length / pageSize);

  // 自动清理
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-gray-50 dark:bg-gray-950 overflow-hidden">
      {/* 顶部固定操作栏 */}
      <div className="flex-none bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <div className="flex items-center justify-between max-w-[1600px] mx-auto">
          <div className="flex items-center space-x-4">
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">召回测试</h1>
            {isProcessing && (
              <div className="flex items-center space-x-3 bg-primary-50 dark:bg-primary-900/30 px-3 py-1.5 rounded-full">
                <Loading size="sm" className="text-primary-600" />
                <span className="text-sm font-medium text-primary-700 dark:text-primary-400">
                  测试中 {status?.progress.toFixed(1)}% 
                  {status?.estimated_remaining_time ? ` (预计剩余 ${Math.ceil(status.estimated_remaining_time)}s)` : ''}
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center space-x-3">
            <Button 
              variant="outline" 
              onClick={handleReset} 
              disabled={isProcessing}
              className="flex items-center"
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              重置
            </Button>
            <Button 
              onClick={handleRun} 
              disabled={isProcessing || loading}
              className="flex items-center"
            >
              <Play className="h-4 w-4 mr-2" />
              运行测试
            </Button>
            <Button 
              variant="outline" 
              onClick={handleExport} 
              disabled={!status?.results?.length || isProcessing}
              className="flex items-center"
            >
              <Download className="h-4 w-4 mr-2" />
              导出 CSV
            </Button>
          </div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 flex overflow-hidden p-6 gap-6 max-w-[1600px] mx-auto w-full">
        {/* 左侧输入区 */}
        <div className="w-1/3 flex flex-col gap-6 overflow-y-auto min-w-[400px]">
          <Card className="flex-none">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center justify-between">
                <span>测试配置</span>
                <Settings2 className="h-4 w-4 text-gray-400" />
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">选择知识库</label>
                <div className="flex flex-wrap gap-2 p-2 border border-gray-200 dark:border-gray-700 rounded-lg max-h-32 overflow-y-auto">
                  {knowledges.map(kb => (
                    <button
                      key={kb.id}
                      onClick={() => {
                        setSelectedKnowledgeIds(prev => 
                          prev.includes(kb.id) ? prev.filter(id => id !== kb.id) : [...prev, kb.id]
                        );
                      }}
                      className={cn(
                        "px-2 py-1 text-xs rounded-md border transition-colors",
                        selectedKnowledgeIds.includes(kb.id)
                          ? "bg-primary-50 border-primary-500 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300"
                          : "bg-white border-gray-200 text-gray-600 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-400"
                      )}
                    >
                      {kb.name}
                    </button>
                  ))}
                  {knowledges.length === 0 && <span className="text-xs text-gray-400">暂无知识库</span>}
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Top-N</label>
                  <Input 
                    type="number" 
                    value={topN} 
                    onChange={e => setTopN(parseInt(e.target.value))}
                    min={1} 
                    max={100}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">阈值</label>
                  <Input 
                    type="number" 
                    value={threshold} 
                    onChange={e => setThreshold(parseFloat(e.target.value))}
                    step={0.05} 
                    min={0} 
                    max={1}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="flex-1 flex flex-col min-h-0">
            <CardHeader className="pb-3 flex-none">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">提问词输入</CardTitle>
                <div className="flex items-center space-x-2">
                  <span className={cn(
                    "text-xs",
                    queriesText.length > 20000 ? "text-red-500 font-bold" : "text-gray-400"
                  )}>
                    {queriesText.length} / 20,000
                  </span>
                  <label className="cursor-pointer">
                    <input 
                      type="file" 
                      className="hidden" 
                      accept=".txt,.csv" 
                      onChange={handleFileUpload}
                      disabled={isProcessing}
                    />
                    <div className="flex items-center text-xs text-primary-600 hover:text-primary-700 dark:text-primary-400">
                      <Upload className="h-3 w-3 mr-1" />
                      批量导入
                    </div>
                  </label>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 p-0 px-6 pb-6">
              <Textarea
                placeholder="每行输入一条提问词..."
                className="h-full resize-y font-mono text-sm leading-6"
                style={{ minHeight: '300px' }}
                value={queriesText}
                onChange={e => {
                  const val = e.target.value;
                  if (val.length <= 20000) {
                    setQueriesText(val);
                  } else {
                    setQueriesText(val.substring(0, 20000));
                    toast.error('已达到字符上限');
                  }
                }}
                disabled={isProcessing}
              />
            </CardContent>
          </Card>
        </div>

        {/* 右侧结果展示区 */}
        <div className="w-2/3 flex flex-col gap-6 overflow-hidden min-w-[800px]">
          {/* 指标卡片 */}
          {status?.summary && (
            <div className="grid grid-cols-5 gap-4">
              {[
                { label: '平均召回率', value: (status.summary.avg_recall * 100).toFixed(1) + '%', icon: <CheckCircle2 className="text-green-500 h-4 w-4" /> },
                { label: '平均准确率', value: (status.summary.avg_precision * 100).toFixed(1) + '%', icon: <Info className="text-blue-500 h-4 w-4" /> },
                { label: '平均 F1', value: status.summary.avg_f1.toFixed(3), icon: <Play className="text-purple-500 h-4 w-4 rotate-90" /> },
                { label: `Top-${topN} 命中`, value: (status.summary.top_n_hit_rate * 100).toFixed(1) + '%', icon: <SearchIcon className="text-primary-500 h-4 w-4" /> },
                { label: '平均耗时', value: (status.summary.avg_latency * 1000).toFixed(0) + 'ms', icon: <AlertCircle className="text-orange-500 h-4 w-4" /> },
              ].map((stat, i) => (
                <Card key={i} className="bg-white dark:bg-gray-900 border-none shadow-sm">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</span>
                      {stat.icon}
                    </div>
                    <div className="text-lg font-bold text-gray-900 dark:text-white">{stat.value}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <Card className="flex-1 flex flex-col overflow-hidden">
            <CardHeader className="pb-3 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">测试结果</CardTitle>
                <div className="flex items-center space-x-3">
                  <div className="relative">
                    <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="关键字过滤..."
                      className="pl-9 h-9 w-64"
                      value={searchTerm}
                      onChange={e => setSearchTerm(e.target.value)}
                    />
                  </div>
                  <Select
                    className="h-9 w-24"
                    value={pageSize}
                    onChange={e => setPageSize(parseInt(e.target.value))}
                  >
                    <option value={50}>50条/页</option>
                    <option value={100}>100条/页</option>
                    <option value={200}>200条/页</option>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto p-0">
              <table className="w-full text-sm text-left border-collapse">
                <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800 z-10">
                  <tr>
                    <th className="px-6 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" onClick={() => { setSortField('query'); setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }}>
                      提问词
                    </th>
                    <th className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 text-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" onClick={() => { setSortField('recall'); setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }}>
                      召回率
                    </th>
                    <th className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 text-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" onClick={() => { setSortField('f1'); setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }}>
                      F1
                    </th>
                    <th className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 text-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" onClick={() => { setSortField('top_n_hit'); setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }}>
                      Top-N
                    </th>
                    <th className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 text-center cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700" onClick={() => { setSortField('latency'); setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc'); }}>
                      耗时
                    </th>
                    <th className="px-6 py-3 border-b border-gray-100 dark:border-gray-700 font-medium text-gray-500 text-right">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedResults.map((item, idx) => (
                    <tr 
                      key={idx} 
                      className={cn(
                        "group hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors border-b border-gray-50 dark:border-gray-800",
                        item.recall === 0 ? "bg-red-50/30 dark:bg-red-900/10" : ""
                      )}
                    >
                      <td className="px-6 py-4 max-w-xs truncate font-medium text-gray-900 dark:text-gray-200">
                        {item.query}
                      </td>
                      <td className="px-4 py-4 text-center">
                        <span className={cn(
                          "px-2 py-0.5 rounded text-xs font-medium",
                          item.recall >= 0.8 ? "text-green-600 bg-green-50" : 
                          item.recall >= 0.5 ? "text-yellow-600 bg-yellow-50" : "text-red-600 bg-red-50"
                        )}>
                          {(item.recall * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="px-4 py-4 text-center text-gray-600 dark:text-gray-400">
                        {item.f1.toFixed(3)}
                      </td>
                      <td className="px-4 py-4 text-center">
                        {item.top_n_hit ? 
                          <CheckCircle2 className="h-4 w-4 text-green-500 mx-auto" /> : 
                          <AlertCircle className="h-4 w-4 text-red-500 mx-auto" />
                        }
                      </td>
                      <td className="px-4 py-4 text-center text-gray-500">
                        {(item.latency * 1000).toFixed(0)}ms
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => setDetailItem(item)}
                          className="text-primary-600 hover:text-primary-700 dark:text-primary-400 p-1 rounded hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {paginatedResults.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                        {isProcessing ? '正在加载结果...' : '暂无数据，请运行测试'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
            {totalPages > 1 && (
              <CardFooter className="flex-none py-3 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  显示第 {(currentPage - 1) * pageSize + 1} 到 {Math.min(currentPage * pageSize, sortedAndFilteredResults.length)} 条，共 {sortedAndFilteredResults.length} 条
                </span>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(prev => prev - 1)}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm font-medium px-2">
                    {currentPage} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage(prev => prev + 1)}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </CardFooter>
            )}
          </Card>
        </div>
      </div>

      {/* 详情弹窗 */}
      <Modal
        isOpen={!!detailItem}
        onClose={() => setDetailItem(null)}
        title="测试详情"
        size="4xl"
      >
        {detailItem && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300">提问词</h4>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm border border-gray-100 dark:border-gray-700">
                  {detailItem.query}
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300">预期文档 ID</h4>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-sm border border-gray-100 dark:border-gray-700 flex flex-wrap gap-2">
                  {detailItem.expected_doc_ids?.length ? detailItem.expected_doc_ids.map(id => (
                    <span key={id} className="bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded text-xs">#{id}</span>
                  )) : <span className="text-gray-400">未设置</span>}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-gray-700 dark:text-gray-300">召回结果 (Top-{topN})</h4>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                {detailItem.retrieved_docs.map((doc, i) => (
                  <div key={i} className="p-4 border border-gray-100 dark:border-gray-800 rounded-xl bg-white dark:bg-gray-900 shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-bold text-gray-400">#{i + 1}</span>
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-200">{doc.filename}</span>
                        {detailItem.expected_doc_ids?.includes(doc.document_id) && (
                          <span className="text-[10px] bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 px-1.5 py-0.5 rounded">命中</span>
                        )}
                      </div>
                      <span className="text-xs font-mono text-primary-600 bg-primary-50 dark:bg-primary-900/30 dark:text-primary-400 px-2 py-0.5 rounded">
                        Score: {doc.score.toFixed(4)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-3 leading-relaxed">
                      {doc.content}
                    </p>
                  </div>
                ))}
                {detailItem.retrieved_docs.length === 0 && (
                  <div className="text-center py-8 text-gray-500 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                    未召回到任何相关文档
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
