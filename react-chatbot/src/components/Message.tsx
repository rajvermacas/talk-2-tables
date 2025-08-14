/**
 * Individual message component using Material UI
 */

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Avatar,
  IconButton,
  Chip,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Person as PersonIcon,
  SmartToy as BotIcon,
  ContentCopy as CopyIcon,
  Schedule as TimeIcon,
} from '@mui/icons-material';
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
          <Box
            key={index}
            component="pre"
            sx={{
              backgroundColor: 'grey.900',
              color: 'common.white',
              p: 2,
              borderRadius: 1,
              my: 1,
              overflow: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              border: '1px solid',
              borderColor: 'grey.700',
            }}
          >
            <code>{codeContent}</code>
          </Box>
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
    <Box 
      sx={{ 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        mb: 3,
        mx: 2,
        maxWidth: '100%'
      }}
    >
      {/* Message Header */}
      <Box 
        sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: 1, 
          mb: 0.5,
          opacity: 0,
          transition: 'opacity 0.2s',
          '&:hover': { opacity: 1 },
          '.message-container:hover &': { opacity: 1 }
        }}
      >
        <Chip
          icon={<TimeIcon fontSize="small" />}
          label={formatTimestamp(message.timestamp)}
          size="small"
          variant="outlined"
          sx={{ fontSize: '0.75rem', height: '24px' }}
        />
        <IconButton
          size="small"
          onClick={() => copyToClipboard(message.content)}
          title="Copy message"
          sx={{ p: 0.5 }}
        >
          <CopyIcon fontSize="small" />
        </IconButton>
      </Box>
      
      {/* Message Content */}
      <Box
        className="message-container"
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
          maxWidth: '70%',
          minWidth: '200px',
          flexDirection: isUser ? 'row-reverse' : 'row',
        }}
      >
        {/* Avatar */}
        <Avatar
          sx={{
            bgcolor: isUser ? 'primary.main' : 'secondary.main',
            width: 32,
            height: 32,
            fontSize: '0.875rem',
            flexShrink: 0,
          }}
        >
          {isUser ? <PersonIcon fontSize="small" /> : <BotIcon fontSize="small" />}
        </Avatar>

        {/* Message Card */}
        <Card
          elevation={1}
          sx={{
            flex: 1,
            bgcolor: isUser ? 'primary.50' : 'background.paper',
            border: 1,
            borderColor: isUser ? 'primary.200' : 'divider',
            '&:hover': {
              elevation: 2,
            },
          }}
        >
          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
            {message.isLoading ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  Thinking...
                </Typography>
              </Box>
            ) : (
              <>
                <Typography variant="body1" sx={{ lineHeight: 1.6 }}>
                  {formatContent(message.content)}
                </Typography>
                
                {/* Show query results if available */}
                {message.queryResult && (
                  <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Query Results:
                    </Typography>
                    <QueryResults queryResult={message.queryResult} />
                  </Box>
                )}
                
                {/* Show error if present */}
                {message.error && (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    {message.error}
                  </Alert>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default Message;