'use client';

import { useState, useEffect, useRef } from 'react';
import { Send, Plus, Trash2, MessageSquare, ChevronDown, ChevronRight, ThumbsUp, ThumbsDown, FileText, StopCircle, Copy, Check } from 'lucide-react';
import toast from 'react-hot-toast';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Button } from '@/components/ui';
import { Loading, EmptyState } from '@/components/ui/loading';
import { ThinkingProcess, StreamingThinkingProcess } from '@/components/thinking-process';
import { cn } from '@/lib/utils';
import { chatApi, sessionApi, robotApi } from '@/api';
import { useChatStore } from '@/stores';
import type { RobotBrief, ChatHistoryItem, RetrievedContext, ChatStreamChunk } from '@/types';

// 渲染 Markdown 内容（支持 LaTeX）
function MarkdownRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      className="prose-chat text-sm"
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code(props) {
          const { children, className, node, ...rest } = props;
          const match = /language-(\w+)/.exec(className || '');
          const isInline = !className && !node?.position?.start.line;
          const language = match ? match[1] : '';
          let codeContent = String(children).replace(/\n$/, '');

          // 复制功能
          const [copied, setCopied] = useState(false);

          const handleCopy = async () => {
            try {
              await navigator.clipboard.writeText(codeContent);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch (err) {
              toast.error('复制失败');
            }
          };

          if (isInline) {
            return (
              <code className="inline-code" {...rest}>
                {children}
              </code>
            );
          }

          return (
            <div className="code-block-wrapper relative rounded-lg overflow-hidden my-3 border border-gray-200 dark:border-gray-700">
              {/* 头部：语言类型 + 复制按钮 */}
              <div className="flex items-center justify-between px-3 py-2 bg-gray-800 dark:bg-gray-900 border-b border-gray-700">
                <span className="text-xs text-gray-400 font-medium uppercase">
                  {language || 'code'}
                </span>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
                  title="复制代码"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-green-400" />
                      <span className="text-green-400">已复制</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>复制</span>
                    </>
                  )}
                </button>
              </div>
              {/* 代码内容 */}
              <SyntaxHighlighter
                {...rest}
                PreTag="div"
                children={codeContent}
                language={language}
                style={oneDark}
                customStyle={{
                  margin: 0,
                  padding: '1rem',
                  backgroundColor: '#1e1e2e',
                  fontSize: '0.875rem',
                  borderRadius: 0,
                }}
                wrapLines={true}
                showLineNumbers={true}
                lineNumberStyle={{ color: '#6b7280', minWidth: '2em', paddingRight: '1em', textAlign: 'right' }}
              />
            </div>
          );
        },
        table(props) {
          return (
            <div className="table-wrapper overflow-x-auto">
              <table {...props} />
            </div>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

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
    isSending,
    setIsSending,
    sidebarOpen,
    resetChat,
    streamingContent,
    reasoningContent,
    isStreamingFinished,
    appendStreamingContent,
    appendReasoningContent,
    setStreamingContent,
    setReasoningContent,
    setStreamingFinished,
    resetStreaming,
  } = useChatStore();

  const [robots, setRobots] = useState<RobotBrief[]>([]);
  const [question, setQuestion] = useState('');
  const [loadingRobots, setLoadingRobots] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [selectedContexts, setSelectedContexts] = useState<RetrievedContext[] | null>(null);
  const streamingStartedRef = useRef<boolean>(false); // 标记流式响应是否已开始
  // 每个消息的折叠状态，使用 Map 存储 message_id -> isFolded
  const [reasoningFoldedMap, setReasoningFoldedMap] = useState<Map<string, boolean>>(new Map());
  const [isNewChat, setIsNewChat] = useState(true); // 标记是否是新对话模式
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionCreatedRef = useRef<boolean>(false); // 跟踪当前请求的会话是否已创建
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // 使用 ref 保存当前消息列表，避免流式响应回调中状态不一致
  const messagesRef = useRef<ChatHistoryItem[]>([]);
  // 标记当前正在流式输出的消息ID
  const streamingMessageIdRef = useRef<string | null>(null);

  // 监听 messages 变化，同步更新 ref
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // 切换某个消息的折叠状态（用于控制是否展开思考过程）
  const toggleReasoningFolded = (messageId: string) => {
    setReasoningFoldedMap((prev) => {
      const newMap = new Map(prev);
      newMap.set(messageId, !newMap.get(messageId));
      return newMap;
    });
  };

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
  }, [messages, streamingContent, reasoningContent]);

  // 在流结束后清理 reasoningContent，但要等到渲染完成
  useEffect(() => {
    if (isStreamingFinished && reasoningContent) {
      // 延迟清理，确保渲染已经完成
      const timer = setTimeout(() => {
        resetStreaming();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isStreamingFinished, reasoningContent, resetStreaming]);

  const loadSessions = async () => {
    if (!currentRobot) return;
    setLoadingSessions(true);
    try {
      const data = await sessionApi.getList({ robot_id: currentRobot.id, status_filter: 'active' });
      setSessions(data.sessions);
      // 不自动选择会话，保留当前状态（新对话模式或已选择的会话）
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
      setIsNewChat(false); // 加载会话消息，非新对话模式
      // 同步更新 store 和 ref
      messagesRef.current = data.messages || [];
      setMessages(data.messages);
    } catch (error) {
      toast.error('加载会话消息失败');
    }
  };

  const handleNewChat = () => {
    resetChat();
    setQuestion('');
    setIsNewChat(true); // 标记为新对话模式
    // 保留会话列表，只清空当前会话状态
    // 同步清空 ref
    messagesRef.current = [];
    // 清除流式消息标记
    streamingMessageIdRef.current = null;
  };

  const handleSelectSession = (sessionId: string) => {
    setIsNewChat(false); // 标记为非新对话模式
    // 取消正在进行的流式请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsSending(false);
    }
    // 清除流式消息标记
    streamingMessageIdRef.current = null;
    loadSessionMessages(sessionId);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await sessionApi.delete(sessionId);
      setSessions((prev) => prev.filter(s => s.session_id !== sessionId));
      if (currentSession?.session_id === sessionId) {
        resetChat();
        // 同步清空 ref
        messagesRef.current = [];
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
    // 注意：不要在这里调用 resetStreaming()
    // 因为 streamingContent 会在消息渲染时被使用
    // 我们在流式响应完成后再重置 streamingContent

    // 确保有有效的会话ID
    let sessionId = currentSession?.session_id;
    if (!sessionId) {
      if (isNewChat) {
        // 新对话模式，不加载旧会话，直接创建新会话
        sessionId = undefined;
        // 加载会话列表更新侧边栏
        try {
          const data = await sessionApi.getList({ robot_id: currentRobot.id, status_filter: 'active' });
          // 检查是否有已存在的活跃会话（可能是上一个问题创建的）
          if (data.sessions.length > 0) {
            // 使用最新的会话
            sessionId = data.sessions[0].session_id;
            const session = data.sessions[0];
            setCurrentSession(session);
            setIsNewChat(false);
            // 加载该会话的消息
            const sessionData = await sessionApi.getById(sessionId);
            messagesRef.current = sessionData.messages || [];
            setMessages(sessionData.messages);
          }
        } catch (error) {
          console.error('加载会话列表失败', error);
        }
      } else {
        // 非新对话模式（用户选择了某个会话），加载会话列表
        try {
          const data = await sessionApi.getList({ robot_id: currentRobot.id, status_filter: 'active' });
          setSessions(data.sessions);
          if (data.sessions.length > 0) {
            sessionId = data.sessions[0].session_id;
            const session = data.sessions[0];
            setCurrentSession(session);
            // 加载该会话的消息
            const sessionData = await sessionApi.getById(sessionId);
            messagesRef.current = sessionData.messages || [];
            setMessages(sessionData.messages);
          }
        } catch (error) {
          toast.error('加载会话失败');
          setIsSending(false);
          return;
        }
      }
    }

    // 创建AbortController用于取消请求
    abortControllerRef.current = new AbortController();
    // 重置会话创建状态
    sessionCreatedRef.current = false;
    // 重置流式开始标记
    streamingStartedRef.current = false;

    // 添加用户消息和助手占位符
    const userMessageId = `temp-${Date.now()}`;
    const assistantMessageId = `temp-${Date.now() + 1}`;

    const userMessage: ChatHistoryItem = {
      message_id: userMessageId,
      role: 'user',
      content: userQuestion,
      created_at: new Date().toISOString(),
    };

    // 总是保留现有消息，只有在开始新对话按钮点击后才清空
    const existingMessages = messages && messages.length > 0 ? [...messages] : [];
    const newMessages: ChatHistoryItem[] = [...existingMessages, userMessage, {
      message_id: assistantMessageId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      reasoning_content: '',
    }];

    // 初始化折叠状态（默认为展开）
    setReasoningFoldedMap(prev => {
      const newMap = new Map(prev);
      newMap.set(assistantMessageId, false);
      return newMap;
    });

    // 同步更新 ref 和 store
    messagesRef.current = newMessages;
    setMessages(newMessages);
    // 标记当前正在流式输出的消息ID
    streamingMessageIdRef.current = assistantMessageId;

    try {
      await chatApi.askStream(
        {
          robot_id: currentRobot.id,
          question: userQuestion,
          session_id: sessionId,
        },
        (chunk: ChatStreamChunk) => {
          // 获取事件类型
          const eventType = (chunk as any)._eventType || '';
          const chunkType = chunk.type;

          // 处理不同的数据类型
          if (chunkType === 'reasoner') {
            // 开始思考过程
            if (!streamingStartedRef.current) {
              streamingStartedRef.current = true;
              // 初始化思考内容
              setReasoningContent('');
            }
          } else if (chunkType === 'text') {
            // 文本内容 - 直接更新最后一条消息的内容
            if (chunk.msg) {
              if (!streamingStartedRef.current) {
                streamingStartedRef.current = true;
                setStreamingContent('');
              }
              appendStreamingContent(chunk.msg);
              // 直接更新最后一条助手消息的内容
              const currentMsgs = [...messagesRef.current];
              if (currentMsgs.length > 0) {
                const lastMsg = currentMsgs[currentMsgs.length - 1];
                if (lastMsg.role === 'assistant') {
                  const updatedMsg = {
                    ...lastMsg,
                    message_id: assistantMessageId,
                    content: (lastMsg.content || '') + chunk.msg,
                  };
                  currentMsgs[currentMsgs.length - 1] = updatedMsg;
                  messagesRef.current = currentMsgs;
                  setMessages(currentMsgs);
                }
              }
            }
          } else if (chunkType === 'think') {
            // 思考过程内容 - 直接更新最后一条消息的 reasoning_content
            if (chunk.content) {
              if (!streamingStartedRef.current) {
                streamingStartedRef.current = true;
                setReasoningContent('');
              }
              appendReasoningContent(chunk.content);
              // 直接更新最后一条助手消息的 reasoning_content
              const currentMsgs = [...messagesRef.current];
              if (currentMsgs.length > 0) {
                const lastMsg = currentMsgs[currentMsgs.length - 1];
                if (lastMsg.role === 'assistant') {
                  const updatedMsg = {
                    ...lastMsg,
                    message_id: assistantMessageId,
                    reasoning_content: (lastMsg.reasoning_content || '') + chunk.content,
                  };
                  currentMsgs[currentMsgs.length - 1] = updatedMsg;
                  messagesRef.current = currentMsgs;
                  setMessages(currentMsgs);
                }
              }
            }
          } else if (chunkType === 'context') {
            // 上下文引用
            const currentMsgs = [...messagesRef.current];
            if (currentMsgs.length > 0) {
              const lastMsg = currentMsgs[currentMsgs.length - 1];
              if (lastMsg.role === 'assistant') {
                // 收集上下文信息
                const existingContexts = lastMsg.contexts || [];
                const chunkAny = chunk as any;
                const newContext: RetrievedContext = {
                  chunk_id: chunkAny.docId || '',
                  document_id: 0,
                  filename: chunk.title || 'unknown',
                  content: chunkAny.content || '',
                  score: chunkAny.ref_source_weight ? chunkAny.ref_source_weight / 5 : 0,
                  source: 'hybrid',
                };
                currentMsgs[currentMsgs.length - 1] = {
                  ...lastMsg,
                  message_id: assistantMessageId,
                  contexts: [...existingContexts, newContext],
                };
                messagesRef.current = currentMsgs;
                setMessages(currentMsgs);
              }
            }
          } else if (chunkType === 'searchGuid') {
            // 搜索结果标题事件，记录引用数量
            console.log('Search results:', chunk.title);
          } else if (chunkType === 'finished') {
            // 流式响应完成
            setStreamingFinished(true);
            abortControllerRef.current = null;
            // 清除流式消息标记
            streamingMessageIdRef.current = null;

            const fullAnswer = (chunk as any).full_answer || streamingContent;
            const fullReasoning = (chunk as any).full_reasoning_content || reasoningContent;
            const tokenUsage = (chunk as any).token_usage;

            const currentMsgs = [...messagesRef.current];
            if (currentMsgs.length > 0) {
              const lastMsg = currentMsgs[currentMsgs.length - 1];
              if (lastMsg.role === 'assistant') {
                currentMsgs[currentMsgs.length - 1] = {
                  ...lastMsg,
                  message_id: assistantMessageId,
                  content: fullAnswer,
                  reasoning_content: fullReasoning,
                  token_usage: tokenUsage,
                };
                messagesRef.current = currentMsgs;
                setMessages(currentMsgs);
              }
            }
          }

          // 更新会话ID（兼容旧格式和新的 finished 事件）
          if (!sessionCreatedRef.current) {
            const sessionId = (chunk as any).session_id || chunk.session_id;
            if (sessionId) {
              sessionCreatedRef.current = true;
              setIsNewChat(false); // 已创建/选择会话，非新对话模式
              const newSession = {
                session_id: sessionId,
                robot_id: currentRobot.id,
                title: userQuestion.slice(0, 50),
                message_count: 2,
                status: 'active' as const,
                is_pinned: false,
                created_at: new Date().toISOString(),
              };
              setCurrentSession(newSession);
              // 只有当会话不存在时才添加到列表，避免重复
              setSessions((prev) => {
                const sessionList = Array.isArray(prev) ? prev : [];
                const exists = sessionList.some(s => s.session_id === sessionId);
                if (exists) {
                  return sessionList;
                }
                return [newSession, ...sessionList];
              });
            }
          }
        },
        (error) => {
          if (error.name !== 'AbortError') {
            toast.error(`流式响应错误: ${error.message}`);
          }
        },
        abortControllerRef.current.signal
      );
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        // 请求被取消，不显示错误
        streamingMessageIdRef.current = null;
        return;
      }
      const message = error instanceof Error ? error.message : '发送失败';
      toast.error(message);
      // 移除助手消息占位符（保留历史消息）
      setMessages((prev) => {
        const messages = Array.isArray(prev) ? [...prev] : [];
        if (messages.length > 0 && messages[messages.length - 1].role === 'assistant') {
          messages.pop();
        }
        return messages;
      });
      streamingMessageIdRef.current = null;
    } finally {
      setIsSending(false);
      abortControllerRef.current = null;
      streamingMessageIdRef.current = null;
      // 注意：不要调用 resetStreaming()，因为 finished 事件已经处理完内容了
      // 流式内容会保留用于显示思考过程
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
            (Array.isArray(messages) ? messages : []).map((message) => (
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
                  {/* 思考过程（如果有） */}
                  {message.role === 'assistant' && (message.reasoning_content || (isSending && reasoningContent && streamingMessageIdRef.current === message.message_id)) && (
                    <ThinkingProcess
                      content={message.reasoning_content || (reasoningContent || '')}
                      isExpanded={!reasoningFoldedMap.get(message.message_id)}
                    />
                  )}

                  {/* Markdown 内容（支持 LaTeX） */}
                  <MarkdownRenderer
                    content={
                      message.role === 'assistant'
                        ? (message.content || (isSending && streamingMessageIdRef.current === message.message_id ? streamingContent : ''))
                        : message.content
                    }
                  />

                  {/* 流式思考过程指示器（仅在发送中且没有完整内容时显示） */}
                  {message.role === 'assistant' && isSending && reasoningContent && !message.reasoning_content && streamingMessageIdRef.current === message.message_id && (
                    <StreamingThinkingProcess content={reasoningContent} isGenerating={true} />
                  )}

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
                  {message.role === 'assistant' && isStreamingFinished && (
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

          {/* 流式加载中指示器 */}
          {isSending && (
            <div className="flex justify-start">
              <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-3">
                <div className="flex items-center space-x-2">
                  <Loading size="sm" />
                  <span className="text-sm text-gray-500">
                    {streamingContent ? '生成中...' : '思考中...'}
                  </span>
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
                rows={1}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 dark:bg-gray-800 dark:text-white h-9 chat-input-no-scrollbar"
                style={{ resize: 'none' }}
                disabled={isSending}
              />
            </div>
            {isSending ? (
              <Button
                onClick={() => {
                  if (abortControllerRef.current) {
                    abortControllerRef.current.abort();
                    abortControllerRef.current = null;
                  }
                  setIsSending(false);
                }}
                variant="warning"
              >
                <StopCircle className="h-5 w-5 mr-1" />
                停止生成
              </Button>
            ) : (
              <Button onClick={handleSend} disabled={!question.trim()}>
                <Send className="h-5 w-5" />
              </Button>
            )}
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
