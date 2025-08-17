/**
 * API service for communicating with FastAPI backend
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { 
  HealthResponse, 
  ApiError 
} from '../types/chat.types';

class ApiService {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8001';
    
    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000, // 30 second timeout
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    });

    // Request interceptor for logging
    this.client.interceptors.request.use(
      (config) => {
        if (process.env.REACT_APP_DEBUG === 'true') {
          console.log('API Request:', config.method?.toUpperCase(), config.url);
        }
        return config;
      },
      (error) => {
        console.error('API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => {
        if (process.env.REACT_APP_DEBUG === 'true') {
          console.log('API Response:', response.status, response.config.url);
        }
        return response;
      },
      (error) => {
        console.error('API Response Error:', error?.response?.status, error?.response?.data);
        return Promise.reject(this.handleApiError(error));
      }
    );
  }

  private handleApiError(error: any): Error {
    if (error.response) {
      // Server responded with error status
      const apiError: ApiError = error.response.data;
      if (apiError?.error?.message) {
        return new Error(apiError.error.message);
      }
      return new Error(`API Error: ${error.response.status} - ${error.response.statusText}`);
    } else if (error.request) {
      // Request was made but no response
      return new Error('Network error: Unable to connect to server');
    } else {
      // Something else happened
      return new Error(`Request error: ${error.message}`);
    }
  }


  /**
   * Send a query using the Multi-MCP Platform (new endpoint)
   */
  async sendPlatformQuery(query: string, user_id?: string, context?: any): Promise<any> {
    try {
      const request = {
        query: query,
        user_id: user_id,
        context: context || {}
      };
      
      const response = await this.client.post('/v2/chat', request);
      return response.data;
    } catch (error) {
      console.error('Platform query error:', error);
      throw error;
    }
  }

  /**
   * Check server health status
   */
  async checkHealth(): Promise<HealthResponse> {
    try {
      const response: AxiosResponse<HealthResponse> = await this.client.get('/health');
      return response.data;
    } catch (error) {
      console.error('Health check error:', error);
      throw error;
    }
  }

  /**
   * Get platform status (Multi-MCP Platform)
   */
  async getPlatformStatus(): Promise<any> {
    try {
      const response = await this.client.get('/platform/status');
      return response.data;
    } catch (error) {
      console.error('Platform status error:', error);
      throw error;
    }
  }

  /**
   * List available models
   */
  async listModels(): Promise<any> {
    try {
      const response = await this.client.get('/models');
      return response.data;
    } catch (error) {
      console.error('List models error:', error);
      throw error;
    }
  }

  /**
   * Test integration endpoints
   */
  async testIntegration(): Promise<any> {
    try {
      const response = await this.client.get('/test/integration');
      return response.data;
    } catch (error) {
      console.error('Integration test error:', error);
      throw error;
    }
  }

  /**
   * Get base URL for debugging
   */
  getBaseURL(): string {
    return this.baseURL;
  }

  /**
   * Test basic connectivity
   */
  async testConnection(): Promise<boolean> {
    try {
      await this.checkHealth();
      return true;
    } catch (error) {
      return false;
    }
  }
}

// Create singleton instance
export const apiService = new ApiService();
export default apiService;