/// <reference types="vite/client" />

interface ImportMetaEnv {
  // FastAPI Server Configuration
  readonly VITE_API_BASE_URL: string
  readonly VITE_OPENAI_API_BASE_URL: string
  
  // WebSocket Configuration
  readonly VITE_WS_URL: string
  
  // Application Configuration
  readonly VITE_CHAT_TITLE: string
  readonly VITE_MAX_MESSAGE_LENGTH: string
  readonly VITE_TYPING_DELAY: string
  
  // Development Settings
  readonly VITE_DEBUG: string
  readonly VITE_LOG_LEVEL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}