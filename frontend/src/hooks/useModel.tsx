import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { api } from '../api/client';
import type { ModelInfo, ModelsResponse } from '../api/types';

interface ModelContextType {
  models: ModelInfo[];
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  loading: boolean;
}

const ModelContext = createContext<ModelContextType | null>(null);

const STORAGE_KEY = 'selected_model';

export function ModelProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModelState] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) || 'default'
  );
  const [loading, setLoading] = useState(true);

  const fetchModels = useCallback(async () => {
    try {
      const res = await api.get<ModelsResponse>('/api/models');
      setModels(res.models);
      // If stored selection is not in the list, reset to default
      const stored = localStorage.getItem(STORAGE_KEY);
      const ids = res.models.map((m) => m.id);
      if (!stored || !ids.includes(stored)) {
        setSelectedModelState(res.default);
        localStorage.setItem(STORAGE_KEY, res.default);
      }
    } catch {
      setModels([{ id: 'default', name: 'default' }]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const setSelectedModel = (model: string) => {
    setSelectedModelState(model);
    localStorage.setItem(STORAGE_KEY, model);
  };

  return (
    <ModelContext.Provider value={{ models, selectedModel, setSelectedModel, loading }}>
      {children}
    </ModelContext.Provider>
  );
}

export function useModel(): ModelContextType {
  const ctx = useContext(ModelContext);
  if (!ctx) throw new Error('useModel must be used within ModelProvider');
  return ctx;
}
