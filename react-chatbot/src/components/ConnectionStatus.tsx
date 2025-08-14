/**
 * Component for displaying connection status to backend services
 */

import React, { useState } from 'react';
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
        return '🟢';
      case 'disconnected':
        return '🔴';
      case 'error':
        return '🟡';
      default:
        return '⚪';
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

  return (
    <div className={`connection-status ${overallStatus} ${className}`}>
      <div className="status-summary" onClick={() => setIsExpanded(!isExpanded)}>
        <span className="status-icon">
          {getStatusIcon(overallStatus)}
        </span>
        <span className="status-text">
          {status.isConnected ? 'All Systems Operational' : 'Connection Issues'}
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRefresh();
          }}
          disabled={isChecking}
          className="refresh-button"
          title="Refresh connection status"
        >
          {isChecking ? '⟳' : '🔄'}
        </button>
        <span className="expand-icon">
          {isExpanded ? '▼' : '▶'}
        </span>
      </div>

      {isExpanded && (
        <div className="status-details">
          <div className="service-status">
            <div className="service-item">
              <span className="service-icon">
                {getStatusIcon(status.fastapi_status)}
              </span>
              <span className="service-name">FastAPI Server</span>
              <span className="service-status-text">
                {getStatusText(status.fastapi_status)}
              </span>
            </div>

            <div className="service-item">
              <span className="service-icon">
                {getStatusIcon(status.mcp_status)}
              </span>
              <span className="service-name">MCP Server</span>
              <span className="service-status-text">
                {getStatusText(status.mcp_status)}
              </span>
            </div>
          </div>

          {status.error && (
            <div className="error-details">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{status.error}</span>
            </div>
          )}

          <div className="status-footer">
            <span className="last-checked">
              Last checked: {formatLastChecked(status.lastChecked)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConnectionStatus;