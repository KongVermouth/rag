'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { 
  ChevronRight, 
  Save, 
  Play, 
  ArrowLeft, 
  Settings, 
  Search, 
  Database, 
  Bot,
  Plus,
  RefreshCcw
} from 'lucide-react';
import { 
  Button, 
  Card, 
  CardHeader, 
  CardTitle, 
  CardContent, 
  Input, 
  Textarea, 
  Select,
  Loading,
  PageLoading
} from '@/components/ui';
import { useBotEditTestStore } from '@/stores';
import { llmApi, knowledgeApi } from '@/api';
import type { LLMBrief, Knowledge } from '@/types';
import { cn } from '@/lib/utils';
import { toast } from 'react-hot-toast';

export default function BotEditWithTestPage() {
  const router = useRouter();
  const params = useParams();
  const robotId = parseInt(params.id as string);
  
  const { 
    botData, 
    draftData, 
    loading, 
    saving, 
    testing, 
    isDirty, 
    testResults,
    init, 
    updateDraft, 
    save, 
    runRecallTest, 
    reset 
  } = useBotEditTestStore();

  // 基础数据选项
  const [llmOptions, setLlmOptions] = useState<LLMBrief[]>([]);
  const [knowledgeOptions, setKnowledgeOptions] = useState<Knowledge[]>([]);
  
  // 测试参数
  const [testQuery, setTestQuery] = useState('');
  const [testTopK, setTestTopK] = useState(5);
  const [testThreshold, setTestThreshold] = useState(0.1);
  
  // 拖拽宽度
  const [leftWidth, setLeftWidth] = useState(50); // 50%
  const isResizing = useRef(false);

  // 初始化
  useEffect(() => {
    if (robotId) {
      init(robotId);
    }
    
    // 获取下拉选项
    const fetchOptions = async () => {
      try {
        const [llms, kbs] = await Promise.all([
          llmApi.getOptions('chat'),
          knowledgeApi.getList({ limit: 100 })
        ]);
        setLlmOptions(llms);
        setKnowledgeOptions(kbs.items);
      } catch (error) {
        console.error('Failed to fetch options', error);
      }
    };
    fetchOptions();

    // 读取存储的宽度
    const savedWidth = localStorage.getItem('bot_edit_split_width');
    if (savedWidth) {
      setLeftWidth(parseFloat(savedWidth));
    }

    return () => reset();
  }, [robotId, init, reset]);

  // 离开守卫
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // 拖拽逻辑
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    const newWidth = (e.clientX / window.innerWidth) * 100;
    if (newWidth > 20 && newWidth < 80) {
      setLeftWidth(newWidth);
    }
  }, []);

  const handleMouseUp = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'default';
    localStorage.setItem('bot_edit_split_width', leftWidth.toString());
  }, [leftWidth]);

  if (loading) return <PageLoading />;
  if (!botData || !draftData) return <div className="p-8 text-center">机器人不存在</div>;

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden bg-gray-50 dark:bg-gray-950">
      {/* 顶部面包屑与操作栏 */}
      <div className="flex-none h-14 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 flex items-center justify-between">
        <div className="flex items-center space-x-2 text-sm">
          <button 
            onClick={() => router.push('/robots')}
            className="text-gray-500 hover:text-primary-600 flex items-center transition-colors"
          >
            <Bot className="h-4 w-4 mr-1" />
            机器人管理
          </button>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <span className="font-medium text-gray-900 dark:text-white truncate max-w-[150px]">{botData.name}</span>
          <ChevronRight className="h-4 w-4 text-gray-300" />
          <span className="text-gray-400">编辑与测试</span>
        </div>
        
        <div className="flex items-center space-x-3">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => {
              if (isDirty) {
                if (confirm('有未保存内容，确定离开？')) {
                  router.push('/robots');
                }
              } else {
                router.push('/robots');
              }
            }}
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            返回列表
          </Button>
          <Button 
            size="sm" 
            onClick={save} 
            loading={saving}
            disabled={!isDirty}
          >
            <Save className="h-4 w-4 mr-1" />
            保存修改
          </Button>
        </div>
      </div>

      {/* 主体分栏区 */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* 左侧编辑面板 */}
        <div 
          className="h-full overflow-y-auto p-6"
          style={{ width: `${leftWidth}%` }}
        >
          <div className="max-w-2xl mx-auto space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Settings className="h-5 w-5 mr-2 text-primary-500" />
                  基础信息配置
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center space-x-4">
                  <div className="flex-none">
                    <div className="h-16 w-16 rounded-full bg-primary-100 dark:bg-primary-900/50 flex items-center justify-center border-2 border-primary-200 dark:border-primary-800 overflow-hidden">
                      {draftData.avatar ? (
                        <img src={draftData.avatar} alt="Avatar" className="h-full w-full object-cover" />
                      ) : (
                        <Bot className="h-8 w-8 text-primary-600" />
                      )}
                    </div>
                  </div>
                  <div className="flex-1">
                    <Input 
                      label="机器人名称"
                      placeholder="给你的机器人起个好听的名字"
                      value={draftData.name || ''}
                      onChange={e => updateDraft({ name: e.target.value })}
                      disabled={saving}
                    />
                  </div>
                </div>

                <Input 
                  label="头像 URL"
                  placeholder="https://example.com/avatar.png"
                  value={draftData.avatar || ''}
                  onChange={e => updateDraft({ avatar: e.target.value })}
                  disabled={saving}
                />

                <Textarea 
                  label="机器人描述"
                  placeholder="简单介绍一下这个机器人的用途"
                  rows={2}
                  value={draftData.description || ''}
                  onChange={e => updateDraft({ description: e.target.value })}
                  disabled={saving}
                />

                <Textarea 
                  label="欢迎语"
                  placeholder="机器人首次对话时的开场白"
                  rows={2}
                  value={draftData.welcome_message || ''}
                  onChange={e => updateDraft({ welcome_message: e.target.value })}
                  disabled={saving}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center">
                  <Database className="h-5 w-5 mr-2 text-primary-500" />
                  知识库与模型
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">关联知识库</label>
                  <div className="grid grid-cols-2 gap-2">
                    {knowledgeOptions.map(kb => (
                      <label 
                        key={kb.id} 
                        className={cn(
                          "flex items-center p-2 rounded-lg border transition-all cursor-pointer",
                          draftData.knowledge_ids?.includes(kb.id)
                            ? "border-primary-500 bg-primary-50 dark:bg-primary-900/20"
                            : "border-gray-200 dark:border-gray-800 hover:border-gray-300"
                        )}
                      >
                        <input 
                          type="checkbox"
                          className="hidden"
                          checked={draftData.knowledge_ids?.includes(kb.id)}
                          onChange={() => {
                            if (saving) return;
                            const ids = draftData.knowledge_ids || [];
                            const newIds = ids.includes(kb.id) 
                              ? ids.filter(id => id !== kb.id)
                              : [...ids, kb.id];
                            updateDraft({ knowledge_ids: newIds });
                          }}
                          disabled={saving}
                        />
                        <div className={cn(
                          "h-4 w-4 rounded border flex items-center justify-center mr-2",
                          draftData.knowledge_ids?.includes(kb.id) ? "bg-primary-500 border-primary-500" : "border-gray-300"
                        )}>
                          {draftData.knowledge_ids?.includes(kb.id) && <Plus className="h-3 w-3 text-white" />}
                        </div>
                        <span className="text-sm truncate">{kb.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <Select 
                  label="对话模型"
                  options={llmOptions.map(o => ({ value: o.id, label: o.name }))}
                  value={draftData.chat_llm_id || ''}
                  onChange={e => updateDraft({ chat_llm_id: parseInt(e.target.value) })}
                  disabled={saving}
                />

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Top-K</label>
                    <Input 
                      type="number" 
                      min={1} 
                      max={20}
                      value={draftData.top_k || 5}
                      onChange={e => updateDraft({ top_k: parseInt(e.target.value) })}
                      disabled={saving}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Temperature</label>
                    <Input 
                      type="number" 
                      step={0.1} 
                      min={0} 
                      max={2}
                      value={draftData.temperature || 0.7}
                      onChange={e => updateDraft({ temperature: parseFloat(e.target.value) })}
                      disabled={saving}
                    />
                  </div>
                </div>

                <Textarea 
                  label="系统提示词 (System Prompt)"
                  placeholder="定义机器人的角色和回答规则..."
                  rows={6}
                  value={draftData.system_prompt || ''}
                  onChange={e => updateDraft({ system_prompt: e.target.value })}
                  disabled={saving}
                />
              </CardContent>
            </Card>
          </div>
        </div>

        {/* 拖拽调节条 */}
        <div 
          className="w-1.5 h-full bg-gray-200 dark:bg-gray-800 hover:bg-primary-400 dark:hover:bg-primary-600 cursor-col-resize transition-colors"
          onMouseDown={handleMouseDown}
        />

        {/* 右侧召回测试面板 */}
        <div 
          className="h-full flex flex-col bg-white dark:bg-gray-900"
          style={{ width: `${100 - leftWidth}%` }}
        >
          <div className="flex-none p-6 border-b border-gray-100 dark:border-gray-800">
            <h3 className="text-lg font-bold flex items-center mb-4">
              <Search className="h-5 w-5 mr-2 text-primary-500" />
              召回效果测试
            </h3>
            <div className="space-y-4">
              <div className="flex space-x-2">
                <div className="flex-1">
                  <Input 
                    placeholder="输入测试问句，查看检索效果..."
                    value={testQuery}
                    onChange={e => setTestQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && runRecallTest(testQuery, testTopK, testThreshold)}
                    disabled={testing}
                  />
                </div>
                <Button 
                  onClick={() => runRecallTest(testQuery, testTopK, testThreshold)}
                  loading={testing}
                  disabled={!testQuery.trim()}
                >
                  <Play className="h-4 w-4 mr-1" />
                  执行测试
                </Button>
              </div>
              <div className="flex items-center space-x-4 text-xs text-gray-500">
                <div className="flex items-center">
                  <span className="mr-2">Top-K:</span>
                  <input 
                    type="number" 
                    className="w-12 bg-transparent border-b border-gray-300 focus:border-primary-500 outline-none disabled:opacity-50" 
                    value={testTopK}
                    onChange={e => setTestTopK(parseInt(e.target.value))}
                    disabled={testing}
                  />
                </div>
                <div className="flex items-center">
                  <span className="mr-2">阈值:</span>
                  <input 
                    type="number" 
                    step={0.05}
                    className="w-12 bg-transparent border-b border-gray-300 focus:border-primary-500 outline-none disabled:opacity-50" 
                    value={testThreshold}
                    onChange={e => setTestThreshold(parseFloat(e.target.value))}
                    disabled={testing}
                  />
                </div>
                <div className="flex-1" />
                <Button variant="outline" size="xs" onClick={() => { setTestQuery(''); setTestResults([]); }}>
                  <RefreshCcw className="h-3 w-3 mr-1" />
                  重置
                </Button>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {testing ? (
              <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                <Loading size="lg" className="mb-4" />
                <p>正在检索相关片段...</p>
              </div>
            ) : testResults.length > 0 ? (
              testResults.map((res, i) => (
                <div key={res.id} className="p-4 rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30 hover:border-primary-200 transition-all">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-gray-400">#{i + 1}</span>
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate max-w-[200px]">
                        {res.filename}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary-100 text-primary-700 dark:bg-primary-900/50 dark:text-primary-300 font-mono">
                        Score: {res.score.toFixed(4)}
                      </span>
                      <Button variant="outline" size="xs" className="h-6 text-[10px]">
                        加入测试集
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed line-clamp-4">
                    {res.content}
                  </p>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-gray-400 border-2 border-dashed border-gray-100 dark:border-gray-800 rounded-2xl">
                <Search className="h-12 w-12 mb-4 opacity-20" />
                <p>暂无测试结果</p>
                <p className="text-xs mt-1">在上方输入问句并开始测试</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// 辅助函数：将 store 的 testResults 设置为空
function setTestResults(results: any[]) {
  useBotEditTestStore.setState({ testResults: results });
}
