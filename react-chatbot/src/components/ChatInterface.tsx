/**
 * Main chat interface component using Material UI
 */

import React from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Container,
  Paper,
  Alert,
  AlertTitle,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { useChat } from '../hooks/useChat';
import { useConnectionStatus } from '../hooks/useConnectionStatus';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import ConnectionStatus from './ConnectionStatus';

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

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* App Bar Header */}
      <AppBar position="static" elevation={2}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            {process.env.REACT_APP_CHAT_TITLE || 'Talk2Tables'}
          </Typography>
          
          <ConnectionStatus
            status={connectionStatus}
            onRefresh={checkStatus}
            isChecking={!isMonitoring}
          />
          
          <IconButton
            color="inherit"
            onClick={handleClearChat}
            disabled={messages.length === 0}
            title="Clear chat history"
            sx={{ ml: 1 }}
          >
            <ClearIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Connection Warning */}
      {!connectionStatus.isConnected && (
        <Alert severity="warning" sx={{ borderRadius: 0 }}>
          <AlertTitle>Connection Issues</AlertTitle>
          Some features may not work properly.
          <IconButton
            size="small"
            onClick={checkStatus}
            sx={{ ml: 1 }}
            title="Retry Connection"
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Alert>
      )}

      {/* Main Chat Area */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Messages Container */}
        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          <MessageList 
            messages={messages}
            isTyping={isTyping}
          />
        </Box>

        {/* Error Display */}
        {error && (
          <Alert 
            severity="error" 
            action={
              <IconButton
                color="inherit"
                size="small"
                onClick={handleRetry}
              >
                <RefreshIcon />
              </IconButton>
            }
            sx={{ mx: 2, mb: 1, borderRadius: 2 }}
          >
            {error}
          </Alert>
        )}

        {/* Input Area */}
        <Paper elevation={3} sx={{ borderRadius: 0 }}>
          <Container maxWidth="md" sx={{ py: 2 }}>
            <MessageInput
              onSendMessage={handleSendMessage}
              disabled={isLoading || !connectionStatus.isConnected}
              placeholder={
                !connectionStatus.isConnected 
                  ? "Connecting to server..." 
                  : "Ask about your database or type SQL..."
              }
              maxLength={parseInt(process.env.REACT_APP_MAX_MESSAGE_LENGTH || '5000')}
            />
          </Container>
        </Paper>
      </Box>
    </Box>
  );
};

export default ChatInterface;