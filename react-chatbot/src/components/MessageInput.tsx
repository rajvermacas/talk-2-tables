/**
 * Input component for sending chat messages
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  maxLength?: number;
  className?: string;
}

const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  disabled = false,
  placeholder = "Ask about your database or type SQL...",
  maxLength = 5000,
  className = ''
}) => {
  const [message, setMessage] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const scrollHeight = textarea.scrollHeight;
      const maxHeight = 200; // Maximum height in pixels
      textarea.style.height = Math.min(scrollHeight, maxHeight) + 'px';
      
      // Expand chat input area if content is substantial
      setIsExpanded(scrollHeight > 60);
    }
  }, []);

  // Adjust height when message changes
  useEffect(() => {
    adjustTextareaHeight();
  }, [message, adjustTextareaHeight]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    if (value.length <= maxLength) {
      setMessage(value);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedMessage = message.trim();
    
    if (trimmedMessage && !disabled) {
      onSendMessage(trimmedMessage);
      setMessage('');
      setIsExpanded(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (but allow Shift+Enter for new line)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
    
    // Handle Escape to clear
    if (e.key === 'Escape') {
      setMessage('');
      setIsExpanded(false);
    }
  };

  const handleClear = () => {
    setMessage('');
    setIsExpanded(false);
    textareaRef.current?.focus();
  };

  const insertSampleQuery = (query: string) => {
    setMessage(query);
    textareaRef.current?.focus();
  };

  const sampleQueries = [
    "SELECT * FROM customers LIMIT 10",
    "Show me the top 5 products by sales",
    "How many orders were placed this month?",
    "What customers have spent the most money?"
  ];

  return (
    <div className={`message-input-container ${isExpanded ? 'expanded' : ''} ${className}`}>
      {/* Sample queries (show when input is empty) */}
      {message === '' && (
        <div className="sample-queries">
          <span className="sample-label">Quick examples:</span>
          {sampleQueries.map((query, index) => (
            <button
              key={index}
              onClick={() => insertSampleQuery(query)}
              className="sample-query-button"
              disabled={disabled}
            >
              {query}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="message-form">
        <div className="input-group">
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            className="message-textarea"
            rows={1}
            autoFocus
          />
          
          <div className="input-actions">
            {message && (
              <button
                type="button"
                onClick={handleClear}
                className="clear-button"
                disabled={disabled}
                title="Clear message (Esc)"
              >
                ✕
              </button>
            )}
            
            <button
              type="submit"
              disabled={disabled || !message.trim()}
              className="send-button"
              title="Send message (Enter)"
            >
              {disabled ? '⏳' : '➤'}
            </button>
          </div>
        </div>

        <div className="input-footer">
          <span className="character-count">
            {message.length}/{maxLength}
          </span>
          
          <span className="input-hint">
            Press Enter to send, Shift+Enter for new line
          </span>
        </div>
      </form>
    </div>
  );
};

export default MessageInput;