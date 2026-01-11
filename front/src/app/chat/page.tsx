'use client';

import { useState, useEffect, useRef } from 'react';
import { Send, Plus, Trash2, MessageSquare, ChevronDown, ThumbsUp, ThumbsDown, FileText } from 'lucide-react';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';
import { Button } from '@/components/ui';
import { Loading, EmptyState } from '@/components/ui/loading';
import { cn } from '@/lib/utils';
import { chatApi, sessionApi, robotApi } from '@/api';
import { useChatStore } from '@/stores';
import type { RobotBrief, ChatHistoryItem, RetrievedContext } from '@/types';

export default function ChatPage() {
  const {
    currentRobot,
    setCurrentRobot,
    currentSession,
    setCurrentSession,
    sessions,
    setSessions,
    messages,
    setMessages,
    addMessage,
    isSending,
    setIsSending,
    sidebarOpen,
    setSidebarOpen,
    resetChat,
  } = useChatStore();

  const [robots, setRobots] = useState<RobotBrief[]>([]);
  const [question, setQuestion] = useState('');
  const [loadingRobots, setLoadingRobots] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [selectedContexts, setSelectedContexts] = useState<RetrievedContext[] | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载机器人列表
  useEffect(() => {
    const loadRobots = async () => {
      try {
        const data = await robotApi.getBriefList();
        setRobots(data);
        if (data.length > 0 && !currentRobot) {
          setCurrentRobot(data[0]);
        }
      } catch (error) {
        toast.error('加载机器人列表失败');
      } finally {
        setLoadingRobots(false);
      }
    };
    loadRobots();
  }, [currentRobot, setCurrentRobot]);

  // 加载会话列表
  useEffect(() => {
    if (currentRobot) {
      loadSessions();
    }
  }, [currentRobot]);

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadSessions = async () => {
    if (!currentRobot) return;
    setLoadingSessions(true);
    try {
      const data = await sessionApi.getList({ robot_id: currentRobot.id, status_filter: 'active' });
      setSessions(data.sessions);
    } catch (error) {
      toast.error('加载会话列表失败');
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const data = await sessionApi.getById(sessionId);
      setCurrentSession(data.session);
      setMessages(data.messages);
    } catch (error) {
      toast.error('加载会话消息失败');
    }
  };

  const handleNewChat = () => {
    resetChat();
    setQuestion('');
  };

  const handleSelectSession = (sessionId: string) => {
    loadSessionMessages(sessionId);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await sessionApi.delete(sessionId);
      setSessions(sessions.filter(s => s.session_id !== sessionId));
      if (currentSession?.session_id === sessionId) {
        resetChat();
      }
      toast.success('会话已删除');
    } catch (error) {
      toast.error('删除会话失败');
    }
  };

  const handleSend = async () => {
    if (!question.trim() || !currentRobot || isSending) return;

    const userQuestion = question.trim();
    setQuestion('');
    setIsSending(true);

    // 添加用户消息到界面
    const userMessage: ChatHistoryItem = {
      message_id: `temp-${Date.now()}`,
      role: 'user',
      content: userQuestion,
      created_at: new Date().toISOString(),
    };
    addMessage(userMessage);

    try {
      const response = await chatApi.ask({
        robot_id: currentRobot.id,
        question: userQuestion,
        session_id: currentSession?.session_id,
      });

      // 更新会话ID
      if (!currentSession) {
        const newSession = {
          session_id: response.session_id,
          robot_id: currentRobot.id,
          title: userQuestion.slice(0, 50),
          message_count: 2,
          status: 'active' as const,
          is_pinned: false,
          created_at: new Date().toISOString(),
        };
        setCurrentSession(newSession);
        loadSessions(); // 刷新会话列表
      }

      // 添加助手消息
      const assistantMessage: ChatHistoryItem = {
        message_id: `temp-${Date.now() + 1}`,
        role: 'assistant',
        content: response.answer,
        contexts: response.contexts,
        token_usage: response.token_usage,
        created_at: new Date().toISOString(),
      };
      addMessage(assistantMessage);
    } catch (error) {
      const message = error instanceof Error ? error.message : '发送失败';
      toast.error(message);
      // 移除用户消息
      setMessages(messages.filter(m => m.message_id !== userMessage.message_id));
    } finally {
      setIsSending(false);
    }
  };

  const handleFeedback = async (messageId: string, feedback: 1 | -1) => {
    try {
      await chatApi.submitFeedback({ message_id: messageId, feedback });
      toast.success('反馈已提交');
    } catch (error) {
      toast.error('反馈提交失败');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (loadingRobots) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loading size="lg" text="加载中..." />
      </div>
    );
  }

  if (robots.length === 0) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <EmptyState
          icon={<MessageSquare className="h-12 w-12" />}
          title="暂无可用机器人"
          description="请先创建机器人后再开始对话"
          action={
            <Button onClick={() => window.location.href = '/robots'}>
              创建机器人
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* 侧边栏 - 会话列表 */}
      <div
        className={cn(
          'w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col transition-all duration-300',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full hidden md:flex md:translate-x-0'
        )}
      >
        {/* 机器人选择 */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <select
            value={currentRobot?.id || ''}
            onChange={(e) => {
              const robot = robots.find(r => r.id === parseInt(e.target.value));
              if (robot) {
                setCurrentRobot(robot);
                resetChat();
              }
            }}
            className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          >
            {robots.map((robot) => (
              <option key={robot.id} value={robot.id}>
                {robot.name}
              </option>
            ))}
          </select>
        </div>

        {/* 新对话按钮 */}
        <div className="p-4">
          <Button onClick={handleNewChat} className="w-full" variant="outline">
            <Plus className="h-4 w-4 mr-2" />
            新对话
          </Button>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto">
          {loadingSessions ? (
            <div className="flex justify-center py-4">
              <Loading size="sm" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="text-center text-gray-500 dark:text-gray-400 py-4 text-sm">
              暂无对话
            </p>
          ) : (
            <div className="space-y-1 px-2">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => handleSelectSession(session.session_id)}
                  className={cn(
                    'group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors',
                    currentSession?.session_id === session.session_id
                      ? 'bg-primary-50 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
                  )}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{session.title || '新对话'}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {session.message_count} 条消息
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(session.session_id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 主聊天区域 */}
      <div className="flex-1 flex flex-col">
        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 dark:text-gray-400">
              <MessageSquare className="h-12 w-12 mb-4" />
              <p>开始一个新对话吧</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.message_id}
                className={cn(
                  'flex message-enter',
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[80%] rounded-lg px-4 py-3',
                    message.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                  )}
                >
                  <ReactMarkdown className="prose-chat text-sm">
                    {message.content}
                  </ReactMarkdown>

                  {/* 引用来源 */}
                  {message.role === 'assistant' && message.contexts && message.contexts.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                      <button
                        onClick={() => setSelectedContexts(message.contexts || null)}
                        className="flex items-center text-xs text-primary-600 dark:text-primary-400 hover:underline"
                      >
                        <FileText className="h-3 w-3 mr-1" />
                        查看 {message.contexts.length} 个引用来源
                      </button>
                    </div>
                  )}

                  {/* 反馈按钮 */}
                  {message.role === 'assistant' && (
                    <div className="flex items-center space-x-2 mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                      <button
                        onClick={() => handleFeedback(message.message_id, 1)}
                        className="p-1 text-gray-400 hover:text-green-500 transition-colors"
                        title="有帮助"
                      >
                        <ThumbsUp className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleFeedback(message.message_id, -1)}
                        className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                        title="没帮助"
                      >
                        <ThumbsDown className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {/* 加载中指示器 */}
          {isSending && (
            <div className="flex justify-start">
              <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-3">
                <div className="flex items-center space-x-2">
                  <Loading size="sm" />
                  <span className="text-sm text-gray-500">思考中...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-end space-x-4">
            <div className="flex-1">
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入你的问题..."
                rows={2}
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white"
                disabled={isSending}
              />
            </div>
            <Button onClick={handleSend} disabled={!question.trim() || isSending}>
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>

      {/* 引用来源弹窗 */}
      {selectedContexts && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setSelectedContexts(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">引用来源</h3>
              <button onClick={() => setSelectedContexts(null)} className="text-gray-400 hover:text-gray-600">
                <ChevronDown className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4">
              {selectedContexts.map((ctx, idx) => (
                <div key={idx} className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{ctx.filename}</span>
                    <span className="text-xs text-primary-600 dark:text-primary-400">
                      相似度: {(ctx.score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{ctx.content}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
