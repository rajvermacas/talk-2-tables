/**
 * Component for displaying the list of chat messages
 */

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from '../types/chat.types';
import Message from './Message';

interface MessageListProps {
  messages: ChatMessage[];
  isTyping?: boolean;
  className?: string;
}

const MessageList: React.FC<MessageListProps> = ({ 
  messages, 
  isTyping = false,
  className = '' 
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const scrollToBottom = () => {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ 
          behavior: 'smooth',
          block: 'end'
        });
      }
    };

    // Small delay to ensure DOM is updated
    const timeoutId = setTimeout(scrollToBottom, 100);
    return () => clearTimeout(timeoutId);
  }, [messages, isTyping]);

  // Handle manual scroll behavior
  const handleScroll = () => {
    // You could implement "scroll to see new messages" indicator here
    // if user has scrolled up and new messages arrive
  };

  if (messages.length === 0) {
    return (
      <div className={`message-list empty ${className}`}>
        <div className="welcome-message">
          <h2>Welcome to Talk2Tables Chat</h2>
          <p>Ask me questions about your database or type SQL queries directly.</p>
          <div className="example-queries">
            <h3>Try asking:</h3>
            <ul>
              <li>"Show me all customers"</li>
              <li>"What are our top selling products?"</li>
              <li>"How many orders were placed last month?"</li>
              <li>Or type SQL directly: "SELECT * FROM customers LIMIT 10"</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className={`message-list ${className}`}
      onScroll={handleScroll}
    >
      <div className="messages-container">
        {messages.map((message) => (
          <Message 
            key={message.id} 
            message={message}
            className="message-item"
          />
        ))}
        
        {/* Typing indicator */}
        {isTyping && (
          <div className="typing-indicator">
            <div className="typing-message">
              <span className="typing-avatar">🤖</span>
              <div className="typing-content">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="typing-text">Assistant is typing...</span>
              </div>
            </div>
          </div>
        )}
        
        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default MessageList;