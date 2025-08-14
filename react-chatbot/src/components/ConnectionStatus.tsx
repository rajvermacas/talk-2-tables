/**
 * Component for displaying connection status using Material UI
 */

import React, { useState } from 'react';
import {
  Box,
  Chip,
  IconButton,
  Collapse,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Alert,
} from '@mui/material';
import {
  CheckCircle as ConnectedIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Wifi as WifiIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { ConnectionStatus as ConnectionStatusType } from '../types/chat.types';

interface ConnectionStatusProps {
  status: ConnectionStatusType;
  onRefresh: () => void;
  isChecking?: boolean;
  className?: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  onRefresh,
  isChecking = false,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getStatusIcon = (connectionStatus: 'connected' | 'disconnected' | 'error') => {
    switch (connectionStatus) {
      case 'connected':
        return <ConnectedIcon fontSize="small" />;
      case 'disconnected':
        return <ErrorIcon fontSize="small" />;
      case 'error':
        return <WarningIcon fontSize="small" />;
      default:
        return <WarningIcon fontSize="small" />;
    }
  };

  const getStatusText = (connectionStatus: 'connected' | 'disconnected' | 'error') => {
    switch (connectionStatus) {
      case 'connected':
        return 'Connected';
      case 'disconnected':
        return 'Disconnected';
      case 'error':
        return 'Error';
      default:
        return 'Unknown';
    }
  };

  const getStatusColor = (connectionStatus: 'connected' | 'disconnected' | 'error') => {
    switch (connectionStatus) {
      case 'connected':
        return 'success';
      case 'disconnected':
        return 'error';
      case 'error':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatLastChecked = (date: Date): string => {
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffSeconds < 60) {
      return 'Just now';
    } else if (diffSeconds < 3600) {
      const minutes = Math.floor(diffSeconds / 60);
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleTimeString();
    }
  };

  const overallStatus = status.isConnected ? 'connected' : 'error';
  const overallColor = getStatusColor(overallStatus);

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {/* Main Status Chip */}
      <Chip
        icon={getStatusIcon(overallStatus)}
        label={status.isConnected ? 'Connected' : 'Offline'}
        size="small"
        variant="filled"
        onClick={() => setIsExpanded(!isExpanded)}
        sx={{
          cursor: 'pointer',
          backgroundColor: status.isConnected ? '#FFFFFF' : '#FFEBEE', // White for connected, light pink for disconnected
          color: status.isConnected ? '#000000' : '#D32F2F', // Black text for connected, red for disconnected
          border: '1px solid',
          borderColor: status.isConnected ? '#E0E0E0' : '#F44336',
          '& .MuiChip-label': {
            px: 1,
            fontWeight: 500,
          },
          '& .MuiSvgIcon-root': {
            color: status.isConnected ? '#4CAF50' : '#F44336', // Green icon for connected, red for disconnected
          },
          '&:hover': {
            backgroundColor: status.isConnected ? '#F5F5F5' : '#FFCDD2',
          },
        }}
      />

      {/* Refresh Button */}
      <IconButton
        size="small"
        onClick={onRefresh}
        disabled={isChecking}
        title="Refresh connection status"
        sx={{ 
          p: 0.5,
          color: '#FFFFFF', // White icon for visibility on red background
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
          '&:disabled': {
            color: 'rgba(255, 255, 255, 0.5)',
          },
        }}
      >
        <RefreshIcon 
          fontSize="small"
          sx={{
            transform: isChecking ? 'rotate(360deg)' : 'none',
            transition: 'transform 1s linear',
          }}
        />
      </IconButton>

      {/* Expand/Collapse Button */}
      <IconButton
        size="small"
        onClick={() => setIsExpanded(!isExpanded)}
        sx={{ 
          p: 0.5,
          color: '#FFFFFF', // White icon for visibility on red background
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
          },
        }}
      >
        {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
      </IconButton>

      {/* Expanded Status Details */}
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <Paper
          elevation={2}
          sx={{
            position: 'absolute',
            top: '100%',
            right: 0,
            mt: 1,
            minWidth: 280,
            zIndex: 1300,
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ p: 2 }}>
            {/* Header */}
            <Typography variant="subtitle2" gutterBottom>
              Service Status
            </Typography>

            {/* Service List */}
            <List dense sx={{ mb: 1 }}>
              <ListItem disablePadding>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <WifiIcon 
                    fontSize="small" 
                    color={getStatusColor(status.fastapi_status) as 'success' | 'error' | 'warning'}
                  />
                </ListItemIcon>
                <ListItemText
                  primary="FastAPI Server"
                  secondary={getStatusText(status.fastapi_status)}
                />
                {getStatusIcon(status.fastapi_status)}
              </ListItem>

              <ListItem disablePadding>
                <ListItemIcon sx={{ minWidth: 36 }}>
                  <StorageIcon 
                    fontSize="small" 
                    color={getStatusColor(status.mcp_status) as 'success' | 'error' | 'warning'}
                  />
                </ListItemIcon>
                <ListItemText
                  primary="MCP Server"
                  secondary={getStatusText(status.mcp_status)}
                />
                {getStatusIcon(status.mcp_status)}
              </ListItem>
            </List>

            {/* Error Details */}
            {status.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                <Typography variant="body2">
                  {status.error}
                </Typography>
              </Alert>
            )}

            {/* Footer */}
            <Typography variant="caption" color="text.secondary">
              Last checked: {formatLastChecked(status.lastChecked)}
            </Typography>
          </Box>
        </Paper>
      </Collapse>
    </Box>
  );
};

export default ConnectionStatus;