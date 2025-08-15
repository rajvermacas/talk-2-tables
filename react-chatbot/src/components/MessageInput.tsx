/**
 * Input component for sending chat messages with modern styling
 */

import React, { useState, useRef } from 'react';
import { Send, X, Sparkles } from 'lucide-react';
import clsx from 'clsx';

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
  const textFieldRef = useRef<HTMLTextAreaElement>(null);

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
      
      // Reset textarea height
      if (textFieldRef.current) {
        textFieldRef.current.style.height = 'auto';
        textFieldRef.current.style.height = '3rem';
      }
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
      if (textFieldRef.current) {
        textFieldRef.current.style.height = 'auto';
        textFieldRef.current.style.height = '3rem';
      }
    }
  };

  const handleClear = () => {
    setMessage('');
    if (textFieldRef.current) {
      textFieldRef.current.style.height = 'auto';
      textFieldRef.current.style.height = '3rem';
      textFieldRef.current.focus();
    }
  };

  const insertSampleQuery = (query: string) => {
    setMessage(query);
    textFieldRef.current?.focus();
  };

  const sampleQueries = [
    "SELECT * FROM customers LIMIT 10",
    "Show top 5 products by sales",
    "How many orders this month?",
    "Who are the highest spenders?"
  ];

  const isMessageEmpty = message.trim().length === 0;

  return (
    <div className="w-full">
      {/* Sample queries (show when input is empty) */}
      {isMessageEmpty && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-4 w-4 text-red-500" />
            <p className="text-sm text-gray-600 dark:text-gray-400 font-medium">Quick examples:</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {sampleQueries.map((query, index) => (
              <button
                key={index}
                onClick={() => insertSampleQuery(query)}
                disabled={disabled}
                className={clsx(
                  'px-3 py-1.5 text-sm rounded-lg border transition-all duration-200',
                  'bg-gray-50 dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100',
                  'hover:border-red-500/50 hover:bg-red-50 dark:hover:bg-gray-600',
                  'focus:outline-none focus:ring-2 focus:ring-red-500/50',
                  'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-gray-300 disabled:hover:bg-gray-50 dark:disabled:hover:border-gray-600 dark:disabled:hover:bg-gray-700'
                )}
              >
                {query}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <textarea
            ref={textFieldRef}
            value={message}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={clsx(
              'w-full resize-none pr-24 py-4 pl-4',
              'bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-xl text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400',
              'focus:border-red-500 focus:ring-1 focus:ring-red-500',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'min-h-[3rem] max-h-32 overflow-y-auto scrollbar-thin shadow-sm'
            )}
            style={{
              height: 'auto',
              minHeight: '3rem'
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = `${Math.min(target.scrollHeight, 128)}px`;
            }}
          />
          
          {/* Action Buttons */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {/* Clear button */}
            {message && (
              <button
                type="button"
                onClick={handleClear}
                disabled={disabled}
                title="Clear message (Esc)"
                className={clsx(
                  'p-2 rounded-lg transition-all duration-200',
                  'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700',
                  'focus:outline-none focus:ring-2 focus:ring-red-500/50',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                <X className="h-4 w-4" />
              </button>
            )}
            
            {/* Send button */}
            <button
              type="submit"
              disabled={disabled || isMessageEmpty}
              title="Send message (Enter)"
              className={clsx(
                'p-2 rounded-lg transition-all duration-200',
                'bg-gradient-to-r from-red-600 to-red-700',
                'hover:from-red-700 hover:to-red-800',
                'text-white shadow-lg hover:shadow-red-500/30',
                'focus:outline-none focus:ring-2 focus:ring-red-500/50',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'disabled:hover:from-red-600 disabled:hover:to-red-700',
                'disabled:hover:shadow-lg'
              )}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Input Footer */}
        <div className="flex justify-between items-center mt-2 px-1">
          <span className={clsx(
            'text-xs',
            message.length > maxLength * 0.9 
              ? 'text-yellow-400' 
              : message.length > maxLength * 0.8 
              ? 'text-orange-400' 
              : 'text-gray-500 dark:text-gray-400'
          )}>
            {message.length}/{maxLength}
          </span>
          
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Press Enter to send, Shift+Enter for new line
          </span>
        </div>
      </form>
    </div>
  );
};

export default MessageInput;