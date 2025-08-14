#!/usr/bin/env python3
"""
Tests for retry logic and exponential backoff functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch
from openai import RateLimitError, APIError
from httpx import HTTPStatusError, Response

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "fastapi_server"))

from fastapi_server.retry_utils import (
    RetryConfig, 
    retry_with_backoff, 
    is_retryable_error, 
    extract_retry_after,
    RetryableClient
)
from fastapi_server.openrouter_client import OpenRouterClient
from fastapi_server.models import ChatMessage


class TestRetryConfig:
    """Test RetryConfig functionality."""
    
    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 30.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True
    
    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=2.0,
            max_delay=60.0,
            backoff_factor=3.0,
            jitter=False
        )
        assert config.max_retries == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 3.0
        assert config.jitter is False
    
    def test_calculate_delay_exponential(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(
            initial_delay=1.0,
            backoff_factor=2.0,
            max_delay=100.0,
            jitter=False
        )
        
        # Test exponential growth
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2
        assert config.calculate_delay(3) == 8.0  # 1.0 * 2^3
    
    def test_calculate_delay_max_cap(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(
            initial_delay=1.0,
            backoff_factor=2.0,
            max_delay=5.0,
            jitter=False
        )
        
        # Should be capped at max_delay
        assert config.calculate_delay(10) == 5.0
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        config = RetryConfig(
            initial_delay=10.0,
            backoff_factor=2.0,
            max_delay=100.0,
            jitter=True
        )
        
        delay = config.calculate_delay(1)  # Base would be 20.0
        # With jitter, should be between 10.0 and 20.0
        assert 10.0 <= delay <= 20.0
    
    def test_calculate_delay_negative_attempt(self):
        """Test delay calculation with negative attempt."""
        config = RetryConfig()
        assert config.calculate_delay(-1) == 0.0


class TestRetryableErrors:
    """Test error classification for retry logic."""
    
    def test_rate_limit_error_retryable(self):
        """Test that RateLimitError is retryable."""
        # Create a mock response for RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        error = RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
        assert is_retryable_error(error) is True
    
    def test_api_error_retryable_status_codes(self):
        """Test APIError with retryable status codes."""
        # Create mock request for APIError
        mock_request = Mock()
        
        # Test retryable status codes
        for status_code in [429, 500, 502, 503, 504]:
            error = APIError("Server error", request=mock_request, body="Server error")
            error.status_code = status_code
            assert is_retryable_error(error) is True
    
    def test_api_error_non_retryable_status_codes(self):
        """Test APIError with non-retryable status codes."""
        # Create mock request for APIError
        mock_request = Mock()
        
        # Test non-retryable status codes
        for status_code in [400, 401, 403]:
            error = APIError("Bad request", request=mock_request, body="Bad request")
            error.status_code = status_code
            assert is_retryable_error(error) is False
    
    def test_connection_errors_retryable(self):
        """Test that connection errors are retryable."""
        assert is_retryable_error(ConnectionError("Connection failed")) is True
        assert is_retryable_error(TimeoutError("Timeout")) is True
        assert is_retryable_error(asyncio.TimeoutError("Async timeout")) is True
    
    def test_http_status_error_retryable(self):
        """Test HTTPStatusError with retryable status codes."""
        # Mock HTTP response
        response = Mock()
        response.status_code = 429
        error = HTTPStatusError("Rate limited", request=Mock(), response=response)
        assert is_retryable_error(error) is True
    
    def test_non_retryable_errors(self):
        """Test that other errors are not retryable."""
        assert is_retryable_error(ValueError("Invalid value")) is False
        assert is_retryable_error(KeyError("Missing key")) is False
        assert is_retryable_error(TypeError("Type error")) is False


class TestRetryAfterExtraction:
    """Test extraction of Retry-After headers."""
    
    def test_extract_retry_after_from_api_error(self):
        """Test extracting retry-after from APIError."""
        # Mock APIError with response headers
        mock_request = Mock()
        error = APIError("Rate limited", request=mock_request, body="Rate limited")
        mock_response = Mock()
        mock_response.headers = {"Retry-After": "30"}
        error.response = mock_response
        
        retry_after = extract_retry_after(error)
        assert retry_after == 30.0
    
    def test_extract_retry_after_from_http_error(self):
        """Test extracting retry-after from HTTPStatusError."""
        mock_response = Mock()
        mock_response.headers = {"retry-after": "60"}
        error = HTTPStatusError("Rate limited", request=Mock(), response=mock_response)
        
        retry_after = extract_retry_after(error)
        assert retry_after == 60.0
    
    def test_extract_retry_after_missing_header(self):
        """Test extraction when header is missing."""
        mock_request = Mock()
        error = APIError("Some error", request=mock_request, body="Some error")
        mock_response = Mock()
        mock_response.headers = {}
        error.response = mock_response
        
        retry_after = extract_retry_after(error)
        assert retry_after is None
    
    def test_extract_retry_after_invalid_value(self):
        """Test extraction with invalid header value."""
        mock_request = Mock()
        error = APIError("Rate limited", request=mock_request, body="Rate limited")
        mock_response = Mock()
        mock_response.headers = {"Retry-After": "invalid"}
        error.response = mock_response
        
        retry_after = extract_retry_after(error)
        assert retry_after is None


class TestRetryDecorator:
    """Test the retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test successful call doesn't trigger retry."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3, initial_delay=0.1))
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test retry occurs on retryable errors."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, initial_delay=0.01))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                mock_response = Mock()
                mock_response.status_code = 429
                raise RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that function fails after max retries."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, initial_delay=0.01))
        async def test_func():
            nonlocal call_count
            call_count += 1
            mock_response = Mock()
            mock_response.status_code = 429
            raise RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
        
        with pytest.raises(RateLimitError):
            await test_func()
        
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test that non-retryable errors don't trigger retry."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=3, initial_delay=0.01))
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid value")
        
        with pytest.raises(ValueError):
            await test_func()
        
        assert call_count == 1  # No retries
    
    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        """Test custom retryable exceptions."""
        call_count = 0
        
        @retry_with_backoff(
            RetryConfig(max_retries=2, initial_delay=0.01),
            retryable_exceptions=[ValueError]
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Custom retryable error")
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 3


class TestRetryableClient:
    """Test RetryableClient functionality."""
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """Test successful execution through RetryableClient."""
        client = RetryableClient(RetryConfig(max_retries=2, initial_delay=0.01))
        
        async def test_func(value):
            return f"result: {value}"
        
        result = await client.execute_with_retry(test_func, "test")
        assert result == "result: test"
    
    @pytest.mark.asyncio
    async def test_execute_with_retry_failure(self):
        """Test failure handling in RetryableClient."""
        client = RetryableClient(RetryConfig(max_retries=1, initial_delay=0.01))
        
        async def test_func():
            mock_response = Mock()
            mock_response.status_code = 429
            raise RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
        
        with pytest.raises(RateLimitError):
            await client.execute_with_retry(test_func)


class TestOpenRouterClientRetry:
    """Test retry functionality in OpenRouterClient."""
    
    @pytest.mark.asyncio
    async def test_openrouter_client_initialization(self):
        """Test OpenRouterClient initializes with retry config."""
        with patch('fastapi_server.openrouter_client.config') as mock_config:
            mock_config.openrouter_api_key = "test-key"
            mock_config.openrouter_model = "test-model"
            mock_config.max_tokens = 100
            mock_config.temperature = 0.7
            mock_config.max_retries = 5
            mock_config.initial_retry_delay = 2.0
            mock_config.max_retry_delay = 60.0
            mock_config.retry_backoff_factor = 3.0
            
            client = OpenRouterClient()
            
            assert client.retry_config.max_retries == 5
            assert client.retry_config.initial_delay == 2.0
            assert client.retry_config.max_delay == 60.0
            assert client.retry_config.backoff_factor == 3.0


class TestIntegration:
    """Integration tests for retry functionality."""
    
    @pytest.mark.asyncio
    async def test_retry_timing(self):
        """Test that retry timing works correctly."""
        start_time = time.time()
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=2, initial_delay=0.1, jitter=False))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                mock_response = Mock()
                mock_response.status_code = 429
                raise RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
            return "success"
        
        result = await test_func()
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 3
        
        # Should have delays of approximately 0.1 + 0.2 = 0.3 seconds
        elapsed = end_time - start_time
        assert elapsed >= 0.25  # Allow some tolerance
        assert elapsed <= 0.5   # But not too much
    
    @pytest.mark.asyncio
    async def test_server_specified_retry_delay(self):
        """Test that server-specified retry delay is respected."""
        call_count = 0
        
        @retry_with_backoff(RetryConfig(max_retries=1, initial_delay=1.0, max_delay=10.0))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Mock error with Retry-After header
                mock_response = Mock()
                mock_response.status_code = 429
                mock_response.headers = {"Retry-After": "0.1"}
                error = RateLimitError("Rate limit exceeded", response=mock_response, body="Rate limit exceeded")
                raise error
            return "success"
        
        start_time = time.time()
        result = await test_func()
        end_time = time.time()
        
        assert result == "success"
        assert call_count == 2
        
        # Should have used server-specified delay of 0.1 seconds
        elapsed = end_time - start_time
        assert elapsed >= 0.05  # At least the specified delay
        assert elapsed <= 0.3   # But not the default 1.0s delay


if __name__ == "__main__":
    pytest.main([__file__, "-v"])