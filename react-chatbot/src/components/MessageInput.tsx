/**
 * Input component for sending chat messages using Material UI
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box,
  TextField,
  Fab,
  IconButton,
  Chip,
  Typography,
  InputAdornment,
} from '@mui/material';
import {
  Send as SendIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';

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
  const textFieldRef = useRef<HTMLInputElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value.length <= maxLength) {
      setMessage(value);
      setIsExpanded(value.split('\n').length > 2 || value.length > 100);
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
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
    textFieldRef.current?.focus();
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
    <Box sx={{ width: '100%' }}>
      {/* Sample queries (show when input is empty) */}
      {isMessageEmpty && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Quick examples:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {sampleQueries.map((query, index) => (
              <Chip
                key={index}
                label={query}
                onClick={() => insertSampleQuery(query)}
                disabled={disabled}
                variant="outlined"
                size="small"
                sx={{
                  cursor: disabled ? 'default' : 'pointer',
                  '&:hover': {
                    bgcolor: disabled ? 'transparent' : 'action.hover',
                  },
                }}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Input Form */}
      <Box component="form" onSubmit={handleSubmit} sx={{ position: 'relative' }}>
        <TextField
          inputRef={textFieldRef}
          fullWidth
          multiline
          minRows={1}
          maxRows={6}
          value={message}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          variant="outlined"
          size="small"
          sx={{
            '& .MuiOutlinedInput-root': {
              pr: message ? 12 : 6, // Space for buttons
              borderRadius: 3,
            },
          }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end" sx={{ alignSelf: 'flex-end', pb: 0.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {/* Clear button */}
                  {message && (
                    <IconButton
                      size="small"
                      onClick={handleClear}
                      disabled={disabled}
                      title="Clear message (Esc)"
                      sx={{ p: 0.5 }}
                    >
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  )}
                  
                  {/* Send button */}
                  <Fab
                    size="small"
                    color="primary"
                    type="submit"
                    disabled={disabled || isMessageEmpty}
                    title="Send message (Enter)"
                    sx={{
                      width: 32,
                      height: 32,
                      minHeight: 32,
                      boxShadow: 1,
                      '&:hover': {
                        boxShadow: 2,
                      },
                    }}
                  >
                    <SendIcon fontSize="small" />
                  </Fab>
                </Box>
              </InputAdornment>
            ),
          }}
        />

        {/* Input Footer */}
        <Box 
          sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            mt: 0.5,
            px: 1,
          }}
        >
          <Typography variant="caption" color="text.secondary">
            {message.length}/{maxLength}
          </Typography>
          
          <Typography variant="caption" color="text.secondary">
            Press Enter to send, Shift+Enter for new line
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default MessageInput;