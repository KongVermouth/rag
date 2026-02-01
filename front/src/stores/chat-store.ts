import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Session, ChatHistoryItem, RobotBrief } from '@/types';

// 简单的 UUID v4 生成器，避免依赖外部包
const generateUUID = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

interface ChatState {
  // 当前选中的机器人
  currentRobot: RobotBrief | null;
  // 当前会话
  currentSession: Session | null;
  // 会话列表
  sessions: Session[];
  // 当前会话的消息历史
  messages: ChatHistoryItem[];
  // 是否正在发送消息
  isSending: boolean;
  // 侧边栏是否展开
  sidebarOpen: boolean;

  // 流式输出相关状态
  streamingContent: string;
  reasoningContent: string;
  isStreamingFinished: boolean;

  // 操作
  setCurrentRobot: (robot: RobotBrief | null) => void;
  setCurrentSession: (session: Session | null) => void;
  setSessions: (sessions: Session[] | ((prev: Session[]) => Session[])) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
  setMessages: (messages: ChatHistoryItem[] | ((prev: ChatHistoryItem[]) => ChatHistoryItem[])) => void;
  addMessage: (message: ChatHistoryItem) => void;
  updateLastMessage: (content: string) => void;
  setIsSending: (sending: boolean) => void;
  setSidebarOpen: (open: boolean) => void;
  resetChat: () => void;
  createNewSession: (robotId: number) => string;

  // 流式输出操作
  setStreamingContent: (content: string) => void;
  appendStreamingContent: (delta: string) => void;
  setReasoningContent: (content: string) => void;
  appendReasoningContent: (delta: string) => void;
  setStreamingFinished: (finished: boolean) => void;
  resetStreaming: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      // 初始状态
      currentRobot: null,
      currentSession: null,
      sessions: [],
      messages: [],
      isSending: false,
      sidebarOpen: true,

      // 流式输出初始状态
      streamingContent: '',
      reasoningContent: '',
      isStreamingFinished: false,

      // 设置当前机器人
      setCurrentRobot: (robot) => set({ currentRobot: robot }),

      // 设置当前会话
      setCurrentSession: (session) => set({ currentSession: session }),

      // 设置会话列表
      setSessions: (sessions) => set((state) => {
        const newSessions = typeof sessions === 'function' ? sessions(state.sessions) : sessions;
        return { sessions: Array.isArray(newSessions) ? newSessions : [] };
      }),

      // 添加会话
      addSession: (session) => set((state) => ({
        sessions: [session, ...state.sessions]
      })),

      // 删除会话
      removeSession: (sessionId) => set((state) => ({
        sessions: state.sessions.filter(s => s.session_id !== sessionId),
        currentSession: state.currentSession?.session_id === sessionId ? null : state.currentSession
      })),

      // 设置消息历史
      setMessages: (messages) => set((state) => {
        const newMessages = typeof messages === 'function' ? messages(state.messages) : messages;
        return { messages: Array.isArray(newMessages) ? newMessages : [] };
      }),

      // 添加消息
      addMessage: (message) => set((state) => ({
        messages: Array.isArray(state.messages) ? [...state.messages, message] : [message]
      })),

      // 更新最后一条消息内容（用于流式响应）
      updateLastMessage: (content) => set((state) => {
        const messages = Array.isArray(state.messages) ? [...state.messages] : [];
        if (messages.length > 0) {
          messages[messages.length - 1] = {
            ...messages[messages.length - 1],
            content
          };
        }
        return { messages };
      }),

      // 设置发送状态
      setIsSending: (sending) => set({ isSending: sending }),

      // 设置侧边栏状态
      setSidebarOpen: (open) => set({ sidebarOpen: open }),

      // 重置聊天状态
      resetChat: () => set({
        currentSession: null,
        messages: [],
        isSending: false,
        streamingContent: '',
        reasoningContent: '',
        isStreamingFinished: false
      }),

      // 原子操作：创建新会话
      createNewSession: (robotId: number) => {
        const sessionId = generateUUID();
        const newSession: Session = {
          session_id: sessionId,
          robot_id: robotId,
          title: '新对话',
          message_count: 0,
          status: 'active',
          is_pinned: false,
          created_at: new Date().toISOString(),
        };
        set({
          currentSession: newSession,
          messages: [],
          isSending: false,
          streamingContent: '',
          reasoningContent: '',
          isStreamingFinished: false
        });
        return sessionId;
      },

      // 流式输出操作
      setStreamingContent: (content) => set({ streamingContent: content }),

      appendStreamingContent: (delta) => set((state) => ({
        streamingContent: state.streamingContent + delta
      })),

      setReasoningContent: (content) => set({ reasoningContent: content }),

      appendReasoningContent: (delta) => set((state) => ({
        reasoningContent: state.reasoningContent + delta
      })),

      setStreamingFinished: (finished) => set({ isStreamingFinished: finished }),

      resetStreaming: () => set({
        streamingContent: '',
        reasoningContent: '',
        isStreamingFinished: false
      }),
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({
        currentSession: state.currentSession,
        sidebarOpen: state.sidebarOpen,
        // 不持久化消息和流式状态，防止 F5 时的奇怪行为
      }),
    }
  )
);
