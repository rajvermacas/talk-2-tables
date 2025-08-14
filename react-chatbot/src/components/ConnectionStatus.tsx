/**
 * Component for displaying connection status with modern Tailwind CSS design
 */

import React, { useState } from 'react';
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Wifi,
  Database,
} from 'lucide-react';
import { ConnectionStatus as ConnectionStatusType } from '../types/chat.types';
import clsx from 'clsx';

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

  const getStatusIcon = (connectionStatus: 'connected' | 'disconnected' | 'error', size = 'h-4 w-4') => {
    const iconClass = size;
    switch (connectionStatus) {
      case 'connected':
        return <CheckCircle className={clsx(iconClass, 'text-green-400')} />;
      case 'disconnected':
        return <AlertCircle className={clsx(iconClass, 'text-red-400')} />;
      case 'error':
        return <AlertTriangle className={clsx(iconClass, 'text-yellow-400')} />;
      default:
        return <AlertTriangle className={clsx(iconClass, 'text-yellow-400')} />;
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

  const getStatusColorClasses = (connectionStatus: 'connected' | 'disconnected' | 'error') => {
    switch (connectionStatus) {
      case 'connected':
        return 'text-green-400 border-green-400/50 bg-green-400/10';
      case 'disconnected':
        return 'text-red-400 border-red-400/50 bg-red-400/10';
      case 'error':
        return 'text-yellow-400 border-yellow-400/50 bg-yellow-400/10';
      default:
        return 'text-gray-400 border-gray-400/50 bg-gray-400/10';
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
    <div className={clsx('relative flex items-center gap-2', className)}>
      {/* Main Status Chip */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={clsx(
          'flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all duration-200 text-sm font-medium',
          'glass-dark hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-primary-500/50',
          getStatusColorClasses(overallStatus)
        )}
      >
        {getStatusIcon(overallStatus)}
        <span>{status.isConnected ? 'Connected' : 'Offline'}</span>
        {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {/* Refresh Button */}
      <button
        onClick={onRefresh}
        disabled={isChecking}
        title="Refresh connection status"
        className={clsx(
          'p-2 rounded-lg transition-all duration-200 text-gray-300 hover:text-white',
          'glass-dark hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-primary-500/50',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
      >
        <RotateCcw 
          className={clsx(
            'h-4 w-4 transition-transform duration-1000',
            isChecking && 'rotate-360'
          )} 
        />
      </button>

      {/* Expanded Status Details */}
      {isExpanded && (
        <div className="absolute top-full right-0 mt-2 w-80 z-50 animate-fade-in">
          <div className="glass-dark rounded-xl border border-gray-700/50 p-4 shadow-2xl">
            {/* Header */}
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              Service Status
            </h3>

            {/* Service List */}
            <div className="space-y-3 mb-4">
              {/* FastAPI Server */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Wifi className={clsx('h-4 w-4', getStatusColorClasses(status.fastapi_status).split(' ')[0])} />
                  <div>
                    <div className="text-sm font-medium text-gray-200">FastAPI Server</div>
                    <div className="text-xs text-gray-400">{getStatusText(status.fastapi_status)}</div>
                  </div>
                </div>
                {getStatusIcon(status.fastapi_status)}
              </div>

              {/* MCP Server */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Database className={clsx('h-4 w-4', getStatusColorClasses(status.mcp_status).split(' ')[0])} />
                  <div>
                    <div className="text-sm font-medium text-gray-200">MCP Server</div>
                    <div className="text-xs text-gray-400">{getStatusText(status.mcp_status)}</div>
                  </div>
                </div>
                {getStatusIcon(status.mcp_status)}
              </div>
            </div>

            {/* Error Details */}
            {status.error && (
              <div className="bg-red-400/10 border border-red-400/50 rounded-lg p-3 mb-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-200">{status.error}</p>
                </div>
              </div>
            )}

            {/* Footer */}
            <p className="text-xs text-gray-500">
              Last checked: {formatLastChecked(status.lastChecked)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConnectionStatus;