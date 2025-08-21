/**
 * Main chat interface component with modern Tailwind CSS design
 */

import React from 'react';
import { RotateCcw, Trash2, AlertTriangle, Sun, Moon } from 'lucide-react';
import { useChat } from '../hooks/useChat';
import { useConnectionStatus } from '../hooks/useConnectionStatus';
import { useTheme } from '../contexts/ThemeContext';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ConnectionStatus from './ConnectionStatus';
import clsx from 'clsx';

interface ChatInterfaceProps {
  className?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '' }) => {
  
  // Theme functionality
  const { isDark, toggleTheme } = useTheme();
  
  // Chat functionality
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    retryLastMessage,
    isTyping
  } = useChat({
    maxMessages: 100,
    persistMessages: true
  });

  // Connection monitoring
  const {
    status: connectionStatus,
    checkStatus,
    isMonitoring
  } = useConnectionStatus({
    checkInterval: 30000, // 30 seconds
    autoStart: true
  });

  const handleSendMessage = async (content: string) => {
    await sendMessage(content);
  };

  const handleClearChat = () => {
    if (window.confirm('Are you sure you want to clear the chat history?')) {
      clearMessages();
    }
  };

  const handleRetry = () => {
    retryLastMessage();
  };

  return (
    <div className={clsx('h-screen flex flex-col overflow-hidden', className)}>
      {/* Header */}
      <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 relative z-10 shadow-sm">
        <div className="flex items-center justify-between px-6 py-4">
          {/* Logo/Title */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-r from-red-600 to-red-700 flex items-center justify-center">
              <span className="text-white font-bold text-sm">T2T</span>
            </div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
              {import.meta.env?.VITE_CHAT_TITLE || process.env.REACT_APP_CHAT_TITLE || 'Talk2Tables'}
            </h1>
          </div>
          
          {/* Header Actions */}
          <div className="flex items-center gap-3">
            <ConnectionStatus
              status={connectionStatus}
              onRefresh={checkStatus}
              isChecking={!isMonitoring}
            />
            
            {/* Dark Mode Toggle */}
            <button
              onClick={toggleTheme}
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className={clsx(
                'p-2 rounded-lg transition-all duration-200',
                'bg-gray-50 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-red-500/50',
                'dark:bg-gray-800 dark:hover:bg-gray-700',
                'text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-gray-100'
              )}
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            
            <button
              onClick={handleClearChat}
              disabled={messages.length === 0}
              title="Clear chat history"
              className={clsx(
                'p-2 rounded-lg transition-all duration-200',
                'bg-gray-50 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-red-500/50',
                'dark:bg-gray-800 dark:hover:bg-gray-700',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-gray-100'
              )}
            >
              <Trash2 className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Connection Warning */}
        {!connectionStatus.isConnected && (
          <div className="bg-yellow-50 dark:bg-yellow-900/20 border-t border-yellow-200 dark:border-yellow-800 px-6 py-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">Connection Issues</p>
                <p className="text-xs text-yellow-700 dark:text-yellow-300">Some features may not work properly.</p>
              </div>
              <button
                onClick={checkStatus}
                title="Retry Connection"
                className="p-1.5 rounded-lg bg-yellow-100 hover:bg-yellow-200 dark:bg-yellow-800 dark:hover:bg-yellow-700 transition-colors"
              >
                <RotateCcw className="h-3 w-3 text-yellow-600 dark:text-yellow-400" />
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Messages Container */}
        <div className="flex-1 overflow-hidden">
          <MessageList 
            messages={messages}
            isTyping={isTyping}
          />
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-4 mb-3">
            <div className="bg-red-50 border border-red-200 rounded-xl p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
                <button
                  onClick={handleRetry}
                  className="p-1.5 rounded-lg bg-red-100 hover:bg-red-200 transition-colors"
                  title="Retry"
                >
                  <RotateCcw className="h-3 w-3 text-red-600" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 relative z-10">
          <div className="max-w-4xl mx-auto p-4">
            <MessageInput
              onSendMessage={handleSendMessage}
              disabled={isLoading || !connectionStatus.isConnected}
              placeholder={
                !connectionStatus.isConnected 
                  ? "Connecting to server..." 
                  : "Ask about your database or type SQL..."
              }
              maxLength={parseInt(import.meta.env?.VITE_MAX_MESSAGE_LENGTH || process.env.REACT_APP_MAX_MESSAGE_LENGTH || '5000')}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;