/**
 * Main chat interface component
 */

import React, { useState } from 'react';
import { useChat } from '../hooks/useChat';
import { useConnectionStatus } from '../hooks/useConnectionStatus';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ConnectionStatus from './ConnectionStatus';
import styles from '../styles/Chat.module.css';

interface ChatInterfaceProps {
  className?: string;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ className = '' }) => {
  
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

  const getConnectionIndicator = () => {
    if (!connectionStatus.isConnected) {
      return (
        <div className={styles.connectionWarning}>
          <span className={styles.warningIcon}>⚠️</span>
          <span>Connection issues detected. Some features may not work properly.</span>
          <button onClick={checkStatus} className={styles.retryConnection}>
            Retry Connection
          </button>
        </div>
      );
    }
    return null;
  };

  return (
    <div className={`${styles.chatInterface} ${className}`}>
      {/* Header */}
      <div className={styles.chatHeader}>
        <div className={styles.headerTitle}>
          <h1>{process.env.REACT_APP_CHAT_TITLE || 'Talk2Tables Chat'}</h1>
          <p>Ask questions about your database or type SQL queries directly</p>
        </div>
        
        <div className={styles.headerActions}>
          <ConnectionStatus
            status={connectionStatus}
            onRefresh={checkStatus}
            isChecking={!isMonitoring}
            className={styles.headerConnectionStatus}
          />
          
          <button
            onClick={handleClearChat}
            className={styles.clearChatButton}
            disabled={messages.length === 0}
            title="Clear chat history"
          >
            🗑️ Clear
          </button>
        </div>
      </div>

      {/* Connection warning */}
      {getConnectionIndicator()}

      {/* Main chat area */}
      <div className={styles.chatMain}>
        {/* Messages */}
        <div className={styles.chatMessages}>
          <MessageList 
            messages={messages}
            isTyping={isTyping}
            className={styles.mainMessageList}
          />
        </div>

        {/* Error handling */}
        {error && (
          <div className={styles.chatError}>
            <div className={styles.errorContent}>
              <span className={styles.errorIcon}>❌</span>
              <span className={styles.errorMessage}>{error}</span>
              <button onClick={handleRetry} className={styles.retryButton}>
                Retry
              </button>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className={styles.chatInput}>
          <MessageInput
            onSendMessage={handleSendMessage}
            disabled={isLoading || !connectionStatus.isConnected}
            placeholder={
              !connectionStatus.isConnected 
                ? "Connecting to server..." 
                : "Ask about your database or type SQL..."
            }
            maxLength={parseInt(process.env.REACT_APP_MAX_MESSAGE_LENGTH || '5000')}
            className={styles.mainMessageInput}
          />
        </div>
      </div>

      {/* Footer */}
      <div className={styles.chatFooter}>
        <div className={styles.footerInfo}>
          <span>Connected to: {process.env.REACT_APP_API_BASE_URL}</span>
          {messages.length > 0 && (
            <span>Messages: {messages.length}</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;