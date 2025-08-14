/**
 * Individual message component with glassmorphism effects
 */

import React from 'react';
import { User, Bot, Copy, Clock, AlertCircle, Loader2 } from 'lucide-react';
import { ChatMessage } from '../types/chat.types';
import QueryResults from './QueryResults';
import clsx from 'clsx';

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
          <div
            key={index}
            className="bg-gray-950 border border-gray-800 rounded-lg p-4 my-3 overflow-auto font-mono text-sm"
          >
            {language && (
              <div className="text-xs text-gray-400 mb-2 font-sans uppercase tracking-wide">
                {language}
              </div>
            )}
            <pre className="text-gray-100 overflow-auto">
              <code>{codeContent}</code>
            </pre>
          </div>
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

  const isUser = message.role === 'user';
  
  return (
    <div className={clsx(
      'group flex flex-col mb-6 px-4 animate-fade-in',
      isUser ? 'items-end' : 'items-start'
    )}>
      {/* Message Header */}
      <div className={clsx(
        'flex items-center gap-2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}>
        <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-gray-800/50 text-xs text-gray-400">
          <Clock className="h-3 w-3" />
          <span>{formatTimestamp(message.timestamp)}</span>
        </div>
        <button
          onClick={() => copyToClipboard(message.content)}
          title="Copy message"
          className="p-1.5 rounded-lg bg-gray-800/50 hover:bg-gray-700/50 transition-colors text-gray-400 hover:text-gray-300"
        >
          <Copy className="h-3 w-3" />
        </button>
      </div>
      
      {/* Message Content */}
      <div className={clsx(
        'flex items-start gap-3 max-w-4xl',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}>
        {/* Avatar */}
        <div className={clsx(
          'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0',
          isUser 
            ? 'bg-gradient-to-r from-primary-600 to-primary-700' 
            : 'bg-gradient-to-r from-gray-600 to-gray-700'
        )}>
          {isUser ? (
            <User className="h-4 w-4 text-white" />
          ) : (
            <Bot className="h-4 w-4 text-white" />
          )}
        </div>

        {/* Message Bubble */}
        <div className={clsx(
          'message-bubble max-w-3xl min-w-0',
          isUser ? 'message-bubble-user' : 'message-bubble-assistant'
        )}>
          {message.isLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              <span className="text-sm text-gray-400">Thinking...</span>
            </div>
          ) : (
            <>
              <div className="text-sm leading-relaxed">
                {formatContent(message.content)}
              </div>
              
              {/* Show query results if available */}
              {message.queryResult && (
                <div className="mt-4 pt-4 border-t border-gray-700/50">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">
                    Query Results:
                  </h4>
                  <QueryResults queryResult={message.queryResult} />
                </div>
              )}
              
              {/* Show error if present */}
              {message.error && (
                <div className="mt-3 bg-red-400/10 border border-red-400/50 rounded-lg p-3">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-red-200">{message.error}</p>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Message;