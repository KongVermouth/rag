import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface FailedUpload {
  id: number;
  fileName: string;
  errorMsg: string;
  knowledgeId: number;
  timestamp: number;
}

interface DocumentState {
  failedUploads: FailedUpload[];
  addFailedUpload: (upload: FailedUpload) => void;
  removeFailedUpload: (id: number) => void;
  clearFailedUploads: (knowledgeId: number) => void;
}

export const useDocumentStore = create<DocumentState>()(
  persist(
    (set) => ({
      failedUploads: [],
      addFailedUpload: (upload) => 
        set((state) => ({
          failedUploads: [
            ...state.failedUploads.filter((u) => u.id !== upload.id),
            upload,
          ],
        })),
      removeFailedUpload: (id) =>
        set((state) => ({
          failedUploads: state.failedUploads.filter((u) => u.id !== id),
        })),
      clearFailedUploads: (knowledgeId) =>
        set((state) => ({
          failedUploads: state.failedUploads.filter((u) => u.knowledgeId !== knowledgeId),
        })),
    }),
    {
      name: 'rag-document-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);
