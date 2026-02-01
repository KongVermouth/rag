import { create } from 'zustand';
import { robotApi } from '@/api';
import type { RobotDetail, RetrievalTestResultItem } from '@/types';
import { toast } from 'react-hot-toast';

interface BotEditTestState {
  robotId: number | null;
  botData: RobotDetail | null;
  draftData: Partial<RobotDetail> | null;
  testResults: RetrievalTestResultItem[];
  loading: boolean;
  saving: boolean;
  testing: boolean;
  isDirty: boolean;
  
  // Actions
  init: (id: number) => Promise<void>;
  updateDraft: (data: Partial<RobotDetail>) => void;
  save: () => Promise<void>;
  runRecallTest: (query: string, topK: number, threshold: number) => Promise<void>;
  reset: () => void;
}

export const useBotEditTestStore = create<BotEditTestState>((set, get) => ({
  robotId: null,
  botData: null,
  draftData: null,
  testResults: [],
  loading: false,
  saving: false,
  testing: false,
  isDirty: false,

  init: async (id: number) => {
    set({ loading: true, robotId: id });
    try {
      const data = await robotApi.getById(id);
      set({ 
        botData: data, 
        draftData: { ...data }, 
        isDirty: false,
        loading: false 
      });
    } catch (error: any) {
      const msg = error.message || '获取机器人详情失败';
      toast.error(msg);
      set({ loading: false });
    }
  },

  updateDraft: (data: Partial<RobotDetail>) => {
    const { draftData } = get();
    set({ 
      draftData: { ...draftData, ...data } as RobotDetail, 
      isDirty: true 
    });
  },

  save: async () => {
    const { robotId, draftData } = get();
    if (!robotId || !draftData) return;

    set({ saving: true });
    try {
      const updated = await robotApi.update(robotId, draftData);
      set({ 
        botData: updated, 
        draftData: { ...updated }, 
        isDirty: false,
        saving: false 
      });
      toast.success('保存成功');
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '保存失败');
      set({ saving: false });
    }
  },

  runRecallTest: async (query: string, topK: number, threshold: number) => {
    const { robotId } = get();
    if (!robotId) return;

    set({ testing: true });
    try {
      const res = await robotApi.retrievalTest(robotId, {
        query,
        top_k: topK,
        threshold
      });
      set({ testResults: res.results, testing: false });
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '测试失败');
      set({ testing: false });
    }
  },

  reset: () => {
    set({
      robotId: null,
      botData: null,
      draftData: null,
      testResults: [],
      loading: false,
      saving: false,
      testing: false,
      isDirty: false
    });
  }
}));
