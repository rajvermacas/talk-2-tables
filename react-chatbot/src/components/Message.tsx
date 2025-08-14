/**
 * Individual message component for chat interface
 */

import React from 'react';
import { ChatMessage } from '../types/chat.types';
import QueryResults from './QueryResults';

interface MessageProps {
  message: ChatMessage;
  className?: string;
}

const Message: React.FC<MessageProps> = ({ message, className = '' }) => {
  const formatTimestamp = (timestamp: Date): string => {
    return timestamp.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  const formatContent = (content: string): React.ReactElement[] => {
    // Split content by code blocks
    const parts = content.split(/(```[\s\S]*?```)/);
    
    return parts.map((part, index) => {
      if (part.startsWith('```') && part.endsWith('```')) {
        // This is a code block
        const code = part.slice(3, -3);
        const [language, ...codeLines] = code.split('\n');
        const codeContent = codeLines.join('\n');
        
        return (
          <pre key={index} className="code-block">
            <code className={`language-${language}`}>
              {codeContent}
            </code>
          </pre>
        );
      } else {
        // Regular text - preserve line breaks
        return (
          <span key={index}>
            {part.split('\n').map((line, lineIndex, array) => (
              <React.Fragment key={lineIndex}>
                {line}
                {lineIndex < array.length - 1 && <br />}
              </React.Fragment>
            ))}
          </span>
        );
      }
    });
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      // You might want to show a toast notification here
      console.log('Message copied to clipboard');
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  return (
    <div className={`message ${message.role} ${className}`}>
      <div className="message-header">
        <span className="message-role">
          {message.role === 'user' ? 'You' : 'Assistant'}
        </span>
        <span className="message-timestamp">
          {formatTimestamp(message.timestamp)}
        </span>
        <button
          onClick={() => copyToClipboard(message.content)}
          className="copy-button"
          title="Copy message"
        >
          📋
        </button>
      </div>
      
      <div className="message-content">
        {message.isLoading ? (
          <div className="loading-indicator">
            <span className="typing-dots">
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
            <span className="loading-text">Thinking...</span>
          </div>
        ) : (
          <>
            <div className="message-text">
              {formatContent(message.content)}
            </div>
            
            {/* Show query results if available */}
            {message.queryResult && (
              <div className="message-query-results">
                <h4>Query Results:</h4>
                <QueryResults queryResult={message.queryResult} />
              </div>
            )}
            
            {/* Show error if present */}
            {message.error && (
              <div className="message-error">
                <span className="error-icon">⚠️</span>
                Error: {message.error}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Message;