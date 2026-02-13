// Auth
export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  username: string;
}

// Upload
export interface ColumnInfo {
  name: string;
  dtype: string;
  nullable: boolean;
  sample_values: unknown[];
}

export interface SniffResult {
  columns: ColumnInfo[];
  sample_rows: Record<string, unknown>[];
  row_count: number;
  recommended_db: 'postgres' | 'mongodb';
  recommendation_reason: string;
}

export interface UploadResponse {
  collection_name: string;
  db_type: string;
  row_count: number;
  column_count: number;
  message: string;
}

// Collections
export interface CollectionSummary {
  name: string;
  db_type: string;
  original_filename: string;
  row_count: number;
  column_count: number;
  description: string;
  is_public: boolean;
  is_own: boolean;
  owner_username: string;
  created_at: string;
}

export interface CollectionDetail extends CollectionSummary {
  columns: ColumnInfo[];
  sample_rows: Record<string, unknown>[];
}

// Chat
export interface VisualizationData {
  chart_type: 'bar' | 'pie' | 'line';
  title: string;
  labels: string[];
  datasets: Array<{
    label: string;
    data: number[];
    backgroundColor?: string[];
  }>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  query?: string | null;
  query_type?: string | null;
  visualization?: VisualizationData | null;
  follow_ups: string[];
  referenced_collections: string[];
  timestamp: string;
}

export interface ChatResponse {
  session_id: string;
  message: ChatMessage;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatHistory {
  session_id: string;
  title: string;
  messages: ChatMessage[];
}
