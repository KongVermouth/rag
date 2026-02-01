/**
 * API 响应通用类型
 */
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  total: number;
  items: T[];
}

export interface MessageResponse {
  message: string;
}

/**
 * 用户相关类型
 */
export interface User {
  id: number;
  username: string;
  email: string;
  role: 'user' | 'admin';
  status: number;
  created_at: string;
  updated_at: string;
}

export interface UserRegister {
  username: string;
  email: string;
  password: string;
  role?: 'user' | 'admin';
}

export interface UserLogin {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserUpdate {
  email?: string;
  role?: 'user' | 'admin';
  status?: number;
}

export interface PasswordChange {
  old_password: string;
  new_password: string;
}

export interface UserListResponse extends PaginatedResponse<User> {}

/**
 * 知识库相关类型
 */
export interface Knowledge {
  id: number;
  name: string;
  embed_llm_id: number;
  chunk_size: number;
  chunk_overlap: number;
  description?: string;
  status: number;
  user_id: number;
  vector_collection_name: string;
  document_count: number;
  total_chunks: number;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeCreate {
  name: string;
  embed_llm_id: number;
  chunk_size?: number;
  chunk_overlap?: number;
  description?: string;
}

export interface KnowledgeUpdate {
  name?: string;
  description?: string;
  status?: number;
}

export interface KnowledgeBrief {
  id: number;
  name: string;
  document_count: number;
}

export interface KnowledgeListResponse extends PaginatedResponse<Knowledge> {}

/**
 * 文档相关类型
 */
export interface Document {
  id: number;
  knowledge_id: number;
  file_name: string;
  file_extension: string;
  file_size: number;
  file_path: string;
  mime_type?: string;
  width?: number;
  height?: number;
  preview_url?: string;
  thumbnail_url?: string;
  status: 'uploading' | 'parsing' | 'embedding' | 'completed' | 'failed';
  chunk_count: number;
  error_msg?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document_id: number;
  filename: string;
  file_size: number;
  preview_url?: string;
  mime_type?: string;
  width?: number;
  height?: number;
  task_id?: string;
  message: string;
}

export interface DocumentStatus {
  document_id: number;
  file_name: string;
  status: string;
  chunk_count: number;
  error_msg?: string;
}

export interface DocumentListResponse extends PaginatedResponse<Document> {}

/**
 * 召回测试相关类型
 */
export interface RecallTestQuery {
  query: string;
  expected_doc_ids?: number[];
}

export interface RecallTestRequest {
  queries: RecallTestQuery[];
  topN: number;
  threshold: number;
  knowledge_ids: number[];
  robot_id?: number;
}

export interface RecallTestResultItem {
  query: string;
  recall: number;
  precision: number;
  f1: number;
  top_n_hit: boolean;
  retrieved_docs: {
    document_id: number;
    filename: string;
    score: number;
    content: string;
  }[];
  expected_doc_ids?: number[];
  latency: number;
}

export interface RecallTestStatusResponse {
  taskId: string;
  status: 'pending' | 'running' | 'finished' | 'failed';
  progress: number;
  estimated_remaining_time?: number;
  results?: RecallTestResultItem[];
  summary?: {
    avg_recall: number;
    avg_precision: number;
    avg_f1: number;
    top_n_hit_rate: number;
    avg_latency: number;
  };
  error?: string;
}

/**
 * 机器人相关类型
 */
export interface Robot {
  id: number;
  name: string;
  avatar?: string;
  chat_llm_id: number;
  rerank_llm_id?: number;
  system_prompt: string;
  welcome_message?: string;
  top_k: number;
  enable_rerank: boolean;
  temperature: number;
  max_tokens: number;
  description?: string;
  status: number;
  user_id: number;
  knowledge_ids: number[];
  created_at: string;
  updated_at: string;
}

export type RobotDetail = Robot;

export interface RobotCreate {
  name: string;
  chat_llm_id: number;
  rerank_llm_id?: number;
  knowledge_ids: number[];
  system_prompt?: string;
  top_k?: number;
  enable_rerank?: boolean;
  temperature?: number;
  max_tokens?: number;
  description?: string;
}

export interface RobotUpdate {
  name?: string;
  chat_llm_id?: number;
  rerank_llm_id?: number;
  knowledge_ids?: number[];
  system_prompt?: string;
  top_k?: number;
  enable_rerank?: boolean;
  temperature?: number;
  max_tokens?: number;
  description?: string;
  status?: number;
}

export interface RobotBrief {
  id: number;
  name: string;
  description?: string;
}

export interface RobotListResponse extends PaginatedResponse<Robot> {}

/**
 * 召回测试相关类型
 */
export interface RetrievalTestRequest {
  query: string;
  top_k: number;
  threshold: number;
}

export interface RetrievalTestResultItem {
  id: string;
  score: number;
  content: string;
  document_id: number;
  filename: string;
}

export interface RetrievalTestResponse {
  results: RetrievalTestResultItem[];
}

/**
 * LLM模型相关类型
 */
export interface LLM {
  id: number;
  name: string;
  model_type: 'embedding' | 'chat' | 'rerank';
  provider: string;
  model_name: string;
  base_url?: string;
  api_version?: string;
  description?: string;
  status: number;
  user_id: number;
  created_at: string;
  updated_at: string;
}

export interface LLMCreate {
  name: string;
  model_type: 'embedding' | 'chat' | 'rerank';
  provider: string;
  model_name: string;
  base_url?: string;
  api_version?: string;
  description?: string;
}

export interface LLMUpdate {
  name?: string;
  base_url?: string;
  api_version?: string;
  description?: string;
  status?: number;
}

export interface LLMBrief {
  id: number;
  name: string;
  model_type: string;
  provider: string;
}

export interface LLMListResponse extends PaginatedResponse<LLM> {}

/**
 * API密钥相关类型
 */
export interface APIKey {
  id: number;
  llm_id: number;
  user_id: number;
  alias: string;
  api_key_masked: string;
  description?: string;
  status: number;
  created_at: string;
  updated_at: string;
}

export interface APIKeyCreate {
  llm_id: number;
  alias: string;
  api_key: string;
  description?: string;
}

export interface APIKeyUpdate {
  alias?: string;
  api_key?: string;
  description?: string;
  status?: number;
}

export interface APIKeyOption {
  id: number;
  llm_id: number;
  llm_name?: string;
  alias: string;
}

export interface APIKeyListResponse extends PaginatedResponse<APIKey> {}

export interface APIKeyOptionsResponse {
  total: number;
  items: APIKeyOption[];
}

/**
 * 聊天相关类型
 */
export interface ChatRequest {
  robot_id: number;
  question: string;
  session_id?: string;
  stream?: boolean;
}

export interface RetrievedContext {
  chunk_id: string;
  document_id: number;
  filename: string;
  content: string;
  score: number;
  source: 'vector' | 'keyword' | 'hybrid';
}

export interface ChatResponse {
  session_id: string;
  question: string;
  answer: string;
  contexts: RetrievedContext[];
  token_usage: Record<string, number>;
  response_time: number;
}

export interface KnowledgeTestRequest {
  knowledge_id: number;
  query: string;
  top_k?: number;
  retrieval_mode?: 'vector' | 'keyword' | 'hybrid';
}

export interface KnowledgeTestResponse {
  query: string;
  retrieval_mode: string;
  results: RetrievedContext[];
  retrieval_time: number;
}

/**
 * 会话相关类型
 */
export interface Session {
  session_id: string;
  robot_id: number;
  title?: string;
  summary?: string;
  message_count: number;
  status: 'active' | 'archived' | 'deleted';
  is_pinned: boolean;
  last_message_at?: string;
  created_at: string;
}

export interface SessionCreate {
  robot_id: number;
  title?: string;
}

export interface SessionUpdate {
  title?: string;
  is_pinned?: boolean;
  status?: 'active' | 'archived' | 'deleted';
}

export interface ChatHistoryItem {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  contexts?: RetrievedContext[];
  token_usage?: Record<string, number>;
  feedback?: number;
  created_at: string;
  reasoning_content?: string;
}

export interface SessionDetail {
  session: Session;
  messages: ChatHistoryItem[];
}

export interface SessionListResponse {
  total: number;
  sessions: Session[];
}

export interface FeedbackRequest {
  message_id: string;
  feedback: -1 | 0 | 1;
  comment?: string;
}

/**
 * 流式响应类型 - 新的 event/data 格式
 */

// 基础事件类型
export interface BaseStreamEvent {
  type: string;
}

// 思考过程事件
export interface ThinkEvent extends BaseStreamEvent {
  type: 'think';
  title: string;
  iconType: number;
  content: string;
  status: 1 | 2; // 1: 进行中, 2: 已完成
}

// 文本事件
export interface TextEvent extends BaseStreamEvent {
  type: 'text';
  msg: string;
}

// 搜索结果引用事件
export interface SearchGuidEvent extends BaseStreamEvent {
  type: 'searchGuid';
  title: string;
  subTitle?: string;
  footnote?: string;
  prompt?: string;
  botPrompt?: string;
  entranceIndex?: number;
  messageId?: string;
  sourceType?: string;
  docs?: SearchDoc[];
  citations?: null;
  hitDeepMode?: boolean;
  hitHelpDraw?: boolean;
  hitDrawMore?: boolean;
  hitSearchAIImg?: boolean;
  topic?: string;
  count?: number;
  deepModeCid?: string;
  aiImageTotal?: number;
  realImageTotal?: number;
  enableFeatures?: string[];
}

// 搜索文档
export interface SearchDoc {
  index: number;
  docId: string;
  title: string;
  url: string;
  sourceType: string;
  quote: string;
  publish_time: string;
  icon_url: string;
  web_site_name: string;
  ref_source_weight: number;
  webSiteSource: string;
  invisibleExt?: Record<string, unknown>;
  resource_type?: string;
  sub_resource_type?: string;
}

// 上下文事件
export interface ContextEvent extends BaseStreamEvent {
  type: 'context';
  index: number;
  docId: string;
  title: string;
  url: string;
  sourceType: string;
  quote: string;
  publish_time: string;
  icon_url: string;
  web_site_name: string;
  ref_source_weight: number;
  content: string;
}

// 完成事件
export interface FinishedEvent extends BaseStreamEvent {
  type: 'finished';
  session_id: string;
  token_usage?: Record<string, number>;
  full_answer: string;
  full_reasoning_content: string;
}

// speech_type 事件负载
export type SpeechTypeEvent = { type: 'reasoner' } | { type: 'text' } | ThinkEvent | SearchGuidEvent | ContextEvent | FinishedEvent;

// 原始 SSE 事件
export interface SSEEvent {
  event: string;
  data: string;
}

// 聊天流式响应数据
export interface ChatStreamChunk {
  // 兼容旧格式
  session_id?: string;
  content?: string | null;
  reasoning_content?: string | null;
  is_finished?: boolean;
  contexts?: RetrievedContext[];
  token_usage?: Record<string, number>;
  full_answer?: string;
  full_reasoning_content?: string;
  retrieval_time?: number;
  error?: string;

  // 新格式字段
  type?: string;
  msg?: string;
  title?: string;
  iconType?: number;
  status?: number;
  index?: number;
  docs?: SearchDoc[];
}

/**
 * 思考过程类型
 */
export interface ReasoningContent {
  content: string;
  is_folded: boolean;
}

/**
 * 扩展的聊天消息项（支持思考过程）
 */
export interface ChatHistoryItemWithReasoning extends ChatHistoryItem {
  reasoning_content?: string;
  is_reasoning_folded?: boolean;
}
