/**
 * Custom hook for chat state management and API interactions
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { ChatMessage, QueryResult } from '../types/chat.types';
import { apiService } from '../services/api';

interface UseChatProps {
  maxMessages?: number;
  persistMessages?: boolean;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  retryLastMessage: () => Promise<void>;
  isTyping: boolean;
}

const STORAGE_KEY = 'talk2tables_chat_messages';

export const useChat = ({
  maxMessages = 100,
  persistMessages = true
}: UseChatProps = {}): UseChatReturn => {
  // Load messages from localStorage if persistence is enabled
  const loadPersistedMessages = useCallback((): ChatMessage[] => {
    if (!persistMessages) return [];
    
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert timestamp strings back to Date objects
        return parsed.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp)
        }));
      }
    } catch (error) {
      console.warn('Failed to load persisted messages:', error);
    }
    return [];
  }, [persistMessages]);

  const [messages, setMessages] = useState<ChatMessage[]>(loadPersistedMessages);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  
  const lastUserMessageRef = useRef<string>('');

  // Persist messages to localStorage when they change
  useEffect(() => {
    if (persistMessages && messages.length > 0) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch (error) {
        console.warn('Failed to persist messages:', error);
      }
    }
  }, [messages, persistMessages]);

  // Helper function to add a message
  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      id: uuidv4(),
      timestamp: new Date(),
      ...message
    };

    setMessages(prev => {
      const updated = [...prev, newMessage];
      // Limit messages to maxMessages if specified
      if (maxMessages > 0 && updated.length > maxMessages) {
        return updated.slice(-maxMessages);
      }
      return updated;
    });

    return newMessage.id;
  }, [maxMessages]);

  // Helper function to update a message
  const updateMessage = useCallback((id: string, updates: Partial<ChatMessage>) => {
    setMessages(prev => prev.map(msg => 
      msg.id === id ? { ...msg, ...updates } : msg
    ));
  }, []);

  // Process query results from assistant response
  const processQueryResults = useCallback((content: string): QueryResult | undefined => {
    try {
      // Look for JSON blocks in the response that might contain query results
      const jsonMatch = content.match(/```json\s*(\{[\s\S]*?\})\s*```/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[1]);
        if (parsed.data && Array.isArray(parsed.data)) {
          return {
            success: true,
            data: parsed.data,
            columns: parsed.columns || Object.keys(parsed.data[0] || {}),
            row_count: parsed.data.length
          };
        }
      }
      
      // Look for other indicators of query results
      if (content.includes('Query executed successfully') || 
          content.includes('rows returned') ||
          content.toLowerCase().includes('select ')) {
        // This might be a query response, but we couldn't parse structured data
        return {
          success: true,
          data: [],
          columns: [],
          row_count: 0
        };
      }
    } catch (error) {
      console.warn('Failed to process query results:', error);
    }
    
    return undefined;
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || isLoading) {
      return;
    }

    // Store the user message for potential retry
    lastUserMessageRef.current = content;
    
    // Clear any previous errors
    setError(null);
    setIsLoading(true);

    // Add user message
    addMessage({
      role: 'user',
      content: content.trim()
    });

    // Add loading assistant message
    const assistantMessageId = addMessage({
      role: 'assistant',
      content: '',
      isLoading: true
    });

    try {
      // Simulate typing delay
      setIsTyping(true);
      await new Promise(resolve => setTimeout(resolve, 
        parseInt(process.env.REACT_APP_TYPING_DELAY || '1000')
      ));
      setIsTyping(false);

      // Send to Multi-MCP Platform endpoint (simpler interface)
      const response = await apiService.sendPlatformQuery(
        content.trim(),
        `user_${Date.now()}`, // Simple user ID
        { 
          chat_history: messages.slice(-5).map(msg => ({ // Include last 5 messages as context
            role: msg.role,
            content: msg.content
          }))
        }
      );

      if (response.success) {
        const assistantResponse = response.response;
        
        // Extract query result if available
        let queryResult = undefined;
        if (response.query_result) {
          queryResult = response.query_result;
        } else {
          queryResult = processQueryResults(assistantResponse);
        }

        // Update the assistant message with the response
        updateMessage(assistantMessageId, {
          content: assistantResponse,
          isLoading: false,
          queryResult
        });
      } else {
        const errorMessage = response.errors?.join('; ') || 'Platform query failed';
        throw new Error(errorMessage);
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      
      // Update the assistant message with error
      updateMessage(assistantMessageId, {
        content: `Sorry, I encountered an error: ${errorMessage}`,
        isLoading: false,
        error: errorMessage
      });
    } finally {
      setIsLoading(false);
      setIsTyping(false);
    }
  }, [messages, isLoading, addMessage, updateMessage, processQueryResults]);

  const retryLastMessage = useCallback(async () => {
    if (lastUserMessageRef.current) {
      await sendMessage(lastUserMessageRef.current);
    }
  }, [sendMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
    if (persistMessages) {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [persistMessages]);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    retryLastMessage,
    isTyping
  };
};