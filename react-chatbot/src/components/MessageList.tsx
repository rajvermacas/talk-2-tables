/**
 * Component for displaying the list of chat messages using Material UI
 */

import React, { useEffect, useRef } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  List,
  ListItem,
  Avatar,
  CircularProgress,
} from '@mui/material';
import {
  SmartToy as BotIcon,
  Chat as ChatIcon,
} from '@mui/icons-material';
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
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.default',
        }}
      >
        <Container maxWidth="md">
          <Box sx={{ textAlign: 'center', py: 8 }}>
            {/* Welcome Header */}
            <Box sx={{ mb: 4 }}>
              <ChatIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
              <Typography variant="h3" component="h1" gutterBottom>
                Welcome to Talk2Tables
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ fontSize: '1.1rem', mb: 4 }}>
                Ask me questions about your database or type SQL queries directly.
              </Typography>
            </Box>

            {/* Example Queries */}
            <Paper 
              elevation={1}
              sx={{ 
                p: 3, 
                textAlign: 'left', 
                maxWidth: 600, 
                mx: 'auto',
                bgcolor: 'background.paper',
                border: 1,
                borderColor: 'divider',
              }}
            >
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <BotIcon color="primary" />
                Try asking:
              </Typography>
              <List dense>
                {[
                  "Show me all customers",
                  "What are our top selling products?",
                  "How many orders were placed last month?",
                  'Or type SQL directly: "SELECT * FROM customers LIMIT 10"'
                ].map((example, index) => (
                  <ListItem key={index} sx={{ py: 0.5, pl: 0 }}>
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      • {example}
                    </Typography>
                  </ListItem>
                ))}
              </List>
            </Paper>
          </Box>
        </Container>
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{
        height: '100%',
        overflow: 'auto',
        bgcolor: 'background.default',
      }}
      onScroll={handleScroll}
    >
      <Container maxWidth="md" sx={{ py: 2 }}>
        {/* Messages */}
        {messages.map((message) => (
          <Message 
            key={message.id} 
            message={message}
          />
        ))}
        
        {/* Typing indicator */}
        {isTyping && (
          <Box 
            sx={{ 
              display: 'flex', 
              alignItems: 'flex-start',
              gap: 1,
              mb: 3,
              mx: 2,
            }}
          >
            {/* Bot Avatar */}
            <Avatar
              sx={{
                bgcolor: 'secondary.main',
                width: 32,
                height: 32,
                fontSize: '0.875rem',
                flexShrink: 0,
              }}
            >
              <BotIcon fontSize="small" />
            </Avatar>

            {/* Typing Content */}
            <Paper
              elevation={1}
              sx={{
                p: 2,
                border: 1,
                borderColor: 'divider',
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                bgcolor: 'background.paper',
              }}
            >
              <CircularProgress size={16} color="secondary" />
              <Typography variant="body2" color="text.secondary">
                Assistant is typing...
              </Typography>
            </Paper>
          </Box>
        )}
        
        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </Container>
    </Box>
  );
};

export default MessageList;