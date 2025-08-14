/**
 * Type definitions for chat interface and API responses
 */

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  error?: string;
  queryResult?: QueryResult;
}

export interface QueryResult {
  success: boolean;
  data?: Array<Record<string, any>>;
  columns?: string[];
  error?: string;
  row_count?: number;
  execution_time?: number;
}

export interface ChatCompletionRequest {
  messages: Array<{
    role: string;
    content: string;
  }>;
  model?: string;
  max_tokens?: number;
  temperature?: number;
  stream?: boolean;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: {
      role: string;
      content: string;
    };
    finish_reason: string | null;
  }>;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface ApiError {
  error: {
    message: string;
    type: string;
    code?: string;
  };
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: number;
  mcp_server_status?: string;
}

export interface ConnectionStatus {
  isConnected: boolean;
  lastChecked: Date;
  error?: string;
  fastapi_status: 'connected' | 'disconnected' | 'error';
  mcp_status: 'connected' | 'disconnected' | 'error';
}