import { create } from 'zustand';
import type { Session, ChatHistoryItem, RobotBrief } from '@/types';

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
  
  // 操作
  setCurrentRobot: (robot: RobotBrief | null) => void;
  setCurrentSession: (session: Session | null) => void;
  setSessions: (sessions: Session[]) => void;
  addSession: (session: Session) => void;
  removeSession: (sessionId: string) => void;
  setMessages: (messages: ChatHistoryItem[]) => void;
  addMessage: (message: ChatHistoryItem) => void;
  updateLastMessage: (content: string) => void;
  setIsSending: (sending: boolean) => void;
  setSidebarOpen: (open: boolean) => void;
  resetChat: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  // 初始状态
  currentRobot: null,
  currentSession: null,
  sessions: [],
  messages: [],
  isSending: false,
  sidebarOpen: true,
  
  // 设置当前机器人
  setCurrentRobot: (robot) => set({ currentRobot: robot }),
  
  // 设置当前会话
  setCurrentSession: (session) => set({ currentSession: session }),
  
  // 设置会话列表
  setSessions: (sessions) => set({ sessions }),
  
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
  setMessages: (messages) => set({ messages }),
  
  // 添加消息
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  
  // 更新最后一条消息内容（用于流式响应）
  updateLastMessage: (content) => set((state) => {
    const messages = [...state.messages];
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
    isSending: false
  }),
}));
