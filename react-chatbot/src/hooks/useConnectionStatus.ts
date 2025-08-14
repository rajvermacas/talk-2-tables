/**
 * Hook for monitoring connection status to FastAPI and MCP servers
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ConnectionStatus } from '../types/chat.types';
import { apiService } from '../services/api';

interface UseConnectionStatusProps {
  checkInterval?: number;
  autoStart?: boolean;
}

interface UseConnectionStatusReturn {
  status: ConnectionStatus;
  checkStatus: () => Promise<void>;
  startMonitoring: () => void;
  stopMonitoring: () => void;
  isMonitoring: boolean;
}

export const useConnectionStatus = ({
  checkInterval = 30000, // 30 seconds
  autoStart = true
}: UseConnectionStatusProps = {}): UseConnectionStatusReturn => {
  const [status, setStatus] = useState<ConnectionStatus>({
    isConnected: false,
    lastChecked: new Date(),
    fastapi_status: 'disconnected',
    mcp_status: 'disconnected'
  });

  const [isMonitoring, setIsMonitoring] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | undefined>(undefined);

  const checkStatus = useCallback(async () => {
    const now = new Date();
    
    try {
      // Check FastAPI server health
      const healthResponse = await apiService.checkHealth();
      const fastapiConnected = healthResponse.status === 'healthy';
      
      let mcpConnected = false;
      let mcpError: string | undefined;

      try {
        // Check MCP server status through FastAPI
        const mcpResponse = await apiService.getMcpStatus();
        mcpConnected = mcpResponse.connected === true;
        if (!mcpConnected && mcpResponse.error) {
          mcpError = mcpResponse.error;
        }
      } catch (mcpErr) {
        mcpError = mcpErr instanceof Error ? mcpErr.message : 'MCP connection failed';
      }

      setStatus({
        isConnected: fastapiConnected && mcpConnected,
        lastChecked: now,
        fastapi_status: fastapiConnected ? 'connected' : 'error',
        mcp_status: mcpConnected ? 'connected' : 'error',
        error: !fastapiConnected 
          ? 'FastAPI server unreachable'
          : !mcpConnected 
            ? `MCP server issue: ${mcpError || 'Connection failed'}`
            : undefined
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Connection check failed';
      
      setStatus({
        isConnected: false,
        lastChecked: now,
        fastapi_status: 'error',
        mcp_status: 'disconnected',
        error: errorMessage
      });
    }
  }, []);

  const startMonitoring = useCallback(() => {
    if (isMonitoring) {
      return; // Already monitoring
    }

    setIsMonitoring(true);
    
    // Initial check
    checkStatus();
    
    // Set up interval
    intervalRef.current = setInterval(checkStatus, checkInterval);
  }, [isMonitoring, checkStatus, checkInterval]);

  const stopMonitoring = useCallback(() => {
    setIsMonitoring(false);
    
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = undefined;
    }
  }, []);

  // Auto-start monitoring if enabled
  useEffect(() => {
    if (autoStart) {
      startMonitoring();
    }

    // Cleanup on unmount
    return () => {
      stopMonitoring();
    };
  }, [autoStart]);

  // Handle window focus - check status when user returns to tab
  useEffect(() => {
    const handleFocus = () => {
      if (isMonitoring) {
        checkStatus();
      }
    };

    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [isMonitoring, checkStatus]);

  return {
    status,
    checkStatus,
    startMonitoring,
    stopMonitoring,
    isMonitoring
  };
};