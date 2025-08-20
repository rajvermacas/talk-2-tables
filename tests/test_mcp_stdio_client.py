"""
Test suite for StdioMCPClient.
Tests written BEFORE implementation (TDD approach).
"""

import pytest
import asyncio
import json
import subprocess
import sys
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from typing import Optional

# These imports will fail initially (RED phase)
from fastapi_server.mcp.clients.stdio_client import (
    StdioMCPClient,
    ProcessError,
    JSONRPCMessage,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
)
from fastapi_server.mcp.clients.base_client import (
    ConnectionResult,
    Tool,
    Resource,
    ToolResult,
    ResourceContent,
    InitializeResult,
    ConnectionState,
    MCPConnectionError,
    MCPTimeoutError,
    MCPProtocolError,
)


class TestJSONRPCMessages:
    """Test JSON-RPC message handling."""
    
    def test_jsonrpc_request(self):
        """Test JSON-RPC request creation."""
        request = JSONRPCRequest(
            id="123",
            method="initialize",
            params={"protocolVersion": "1.0"}
        )
        assert request.jsonrpc == "2.0"
        assert request.id == "123"
        assert request.method == "initialize"
        assert request.params["protocolVersion"] == "1.0"
        
        # Test serialization
        json_str = request.to_json()
        parsed = json.loads(json_str)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "123"
    
    def test_jsonrpc_response(self):
        """Test JSON-RPC response parsing."""
        # Success response
        response = JSONRPCResponse(
            id="123",
            result={"status": "ok"}
        )
        assert response.id == "123"
        assert response.result["status"] == "ok"
        assert response.error is None
        
        # Error response
        error_response = JSONRPCResponse(
            id="124",
            error=JSONRPCError(
                code=-32600,
                message="Invalid Request",
                data={"details": "Missing method"}
            )
        )
        assert error_response.id == "124"
        assert error_response.result is None
        assert error_response.error.code == -32600
        assert error_response.error.message == "Invalid Request"
    
    def test_jsonrpc_error(self):
        """Test JSON-RPC error structure."""
        error = JSONRPCError(
            code=-32700,
            message="Parse error",
            data={"position": 42}
        )
        assert error.code == -32700
        assert error.message == "Parse error"
        assert error.data["position"] == 42
        
        # Standard error codes
        assert JSONRPCError.PARSE_ERROR == -32700
        assert JSONRPCError.INVALID_REQUEST == -32600
        assert JSONRPCError.METHOD_NOT_FOUND == -32601
        assert JSONRPCError.INVALID_PARAMS == -32602
        assert JSONRPCError.INTERNAL_ERROR == -32603
    
    def test_message_framing(self):
        """Test message framing for stdio transport."""
        request = JSONRPCRequest(
            id="1",
            method="test",
            params={}
        )
        
        # Frame the message
        framed = JSONRPCMessage.frame(request.to_json())
        assert framed.endswith("\n")
        
        # Parse framed message
        parsed = JSONRPCMessage.parse_line(framed)
        assert parsed["id"] == "1"
        assert parsed["method"] == "test"


class TestStdioMCPClient:
    """Test suite for stdio MCP client."""
    
    @pytest.fixture
    def client(self):
        """Create stdio client instance."""
        return StdioMCPClient(
            name="test-stdio",
            config={
                "command": "npx",
                "args": ["@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "test-token"},
                "cwd": "/tmp",
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 1.0,
                "buffer_size": 8192,
            }
        )
    
    @pytest.mark.asyncio
    async def test_connect_process_start(self, client):
        """Test subprocess creation and connection."""
        mock_process = AsyncMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.stderr = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await client.connect()
            
            assert result.success is True
            assert client.state == ConnectionState.CONNECTED
            assert client._process == mock_process
            assert client._process.pid == 12345
    
    @pytest.mark.asyncio
    async def test_connect_process_failure(self, client):
        """Test handling process startup failure."""
        with patch('asyncio.create_subprocess_exec', 
                  side_effect=FileNotFoundError("Command not found")):
            result = await client.connect()
            
            assert result.success is False
            assert "Command not found" in result.error
            assert client.state == ConnectionState.ERROR
    
    @pytest.mark.asyncio
    async def test_connect_with_environment(self, client):
        """Test environment variable injection."""
        captured_env = None
        
        async def mock_create_subprocess(*args, **kwargs):
            nonlocal captured_env
            captured_env = kwargs.get('env', {})
            mock_process = AsyncMock()
            mock_process.returncode = None
            return mock_process
        
        with patch('asyncio.create_subprocess_exec', mock_create_subprocess):
            await client.connect()
            
            assert "GITHUB_TOKEN" in captured_env
            assert captured_env["GITHUB_TOKEN"] == "test-token"
            # Should also include current environment
            assert "PATH" in captured_env
    
    @pytest.mark.asyncio
    async def test_disconnect_process_termination(self, client):
        """Test graceful process termination."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock(return_value=0)
        mock_process.kill = Mock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            await client.disconnect()
            
            # Should terminate gracefully first
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once()
            assert client.state == ConnectionState.DISCONNECTED
            assert client._process is None
    
    @pytest.mark.asyncio
    async def test_disconnect_force_kill(self, client):
        """Test force killing process if termination fails."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = Mock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            client.config["shutdown_timeout"] = 0.1
            await client.disconnect()
            
            # Should force kill after timeout
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_receive_messages(self, client):
        """Test sending and receiving JSON-RPC messages."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        
        # Mock stdin write
        written_data = []
        async def mock_write(data):
            written_data.append(data)
        
        mock_process.stdin.write = mock_write
        mock_process.stdin.drain = AsyncMock()
        
        # Mock stdout read
        async def mock_readline():
            return json.dumps({
                "jsonrpc": "2.0",
                "id": "1",
                "result": {"status": "ok"}
            }).encode() + b"\n"
        
        mock_process.stdout.readline = mock_readline
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Send request
            request_id = await client._send_request("test", {"param": "value"})
            
            # Verify message was written
            assert len(written_data) == 1
            sent_msg = json.loads(written_data[0].decode())
            assert sent_msg["method"] == "test"
            assert sent_msg["params"]["param"] == "value"
            
            # Receive response
            response = await client._receive_response(request_id)
            assert response["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_initialize_over_stdio(self, client):
        """Test MCP initialization over stdio."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        
        # Mock response
        async def mock_readline():
            return json.dumps({
                "jsonrpc": "2.0",
                "id": "init-1",
                "result": {
                    "protocolVersion": "1.0",
                    "capabilities": {"tools": True}
                }
            }).encode() + b"\n"
        
        mock_process.stdout.readline = mock_readline
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Mock the response correlation
            client._wait_for_response = AsyncMock(
                return_value={
                    "protocolVersion": "1.0",
                    "capabilities": {"tools": True}
                }
            )
            
            result = await client.initialize()
            assert result.protocolVersion == "1.0"
            assert result.capabilities["tools"] is True
    
    @pytest.mark.asyncio
    async def test_list_tools_over_stdio(self, client):
        """Test listing tools over stdio."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Mock response
            client._wait_for_response = AsyncMock(
                return_value=[
                    {"name": "tool1", "description": "Tool 1", "parameters": {}},
                    {"name": "tool2", "description": "Tool 2", "parameters": {}}
                ]
            )
            
            tools = await client.list_tools()
            assert len(tools) == 2
            assert tools[0].name == "tool1"
    
    @pytest.mark.asyncio
    async def test_call_tool_over_stdio(self, client):
        """Test tool execution over stdio."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Mock response
            client._wait_for_response = AsyncMock(
                return_value={
                    "content": "Tool executed",
                    "isError": False
                }
            )
            
            result = await client.call_tool("test_tool", {"arg": "value"})
            assert result.isError is False
            assert result.content == "Tool executed"
    
    @pytest.mark.asyncio
    async def test_handle_process_crash(self, client):
        """Test handling of process crash."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        # Simulate crash
        async def mock_wait():
            mock_process.returncode = 1
            return 1
        
        mock_process.wait = mock_wait
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Start monitoring
            monitor_task = asyncio.create_task(client._monitor_process())
            
            # Wait for crash detection
            await asyncio.sleep(0.1)
            
            assert client.state == ConnectionState.ERROR
            assert client._process is None
            
            monitor_task.cancel()
    
    @pytest.mark.asyncio
    async def test_handle_stderr_output(self, client):
        """Test handling stderr output from process."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        stderr_lines = []
        
        async def mock_stderr_readline():
            if not stderr_lines:
                stderr_lines.append(1)
                return b"ERROR: Something went wrong\n"
            await asyncio.sleep(10)  # Block after first line
        
        mock_process.stderr.readline = mock_stderr_readline
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Start stderr reader
            reader_task = asyncio.create_task(client._read_stderr())
            
            # Wait for stderr to be read
            await asyncio.sleep(0.1)
            
            # Check that error was logged
            assert len(client._stderr_buffer) > 0
            assert "Something went wrong" in client._stderr_buffer[0]
            
            reader_task.cancel()
    
    @pytest.mark.asyncio
    async def test_buffer_management(self, client):
        """Test stdin/stdout buffer management."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        
        # Test buffer size limits
        large_data = "x" * (client.config["buffer_size"] * 2)
        
        async def mock_write(data):
            if len(data) > client.config["buffer_size"]:
                raise ValueError("Buffer overflow")
        
        mock_process.stdin.write = mock_write
        mock_process.stdin.drain = AsyncMock()
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Should handle large messages properly
            with pytest.raises(ProcessError, match="Message too large"):
                await client._send_request("test", {"data": large_data})
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client):
        """Test handling concurrent requests over stdio."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        responses = {
            "req-1": {"result": "response1"},
            "req-2": {"result": "response2"},
            "req-3": {"result": "response3"}
        }
        
        async def mock_readline():
            # Return responses out of order
            for req_id in ["req-2", "req-1", "req-3"]:
                yield json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": responses[req_id]
                }).encode() + b"\n"
        
        mock_process.stdout.readline = mock_readline().__anext__
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            # Send concurrent requests
            async def make_request(req_id):
                client._pending_requests[req_id] = asyncio.Future()
                # Simulate receiving response
                await asyncio.sleep(0.1)
                client._pending_requests[req_id].set_result(responses[req_id])
                return responses[req_id]
            
            results = await asyncio.gather(
                make_request("req-1"),
                make_request("req-2"),
                make_request("req-3")
            )
            
            # Verify all responses received correctly
            assert results[0] == responses["req-1"]
            assert results[1] == responses["req-2"]
            assert results[2] == responses["req-3"]
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test request timeout handling."""
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdin.write = AsyncMock()
        mock_process.stdin.drain = AsyncMock()
        
        # Mock slow response
        async def mock_readline():
            await asyncio.sleep(10)
            return b'{"jsonrpc": "2.0", "id": "1", "result": {}}\n'
        
        mock_process.stdout.readline = mock_readline
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            await client.connect()
            
            client.config["timeout"] = 0.1
            
            with pytest.raises(MCPTimeoutError):
                await client._wait_for_response("test-req", timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_process_restart(self, client):
        """Test restarting process after crash."""
        call_count = 0
        
        async def mock_create_process(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_process = AsyncMock()
            mock_process.returncode = None
            mock_process.stdin.write = AsyncMock()
            mock_process.stdin.drain = AsyncMock()
            
            if call_count == 1:
                # First process crashes
                mock_process.returncode = 1
            
            return mock_process
        
        with patch('asyncio.create_subprocess_exec', mock_create_process):
            # First connection
            await client.connect()
            assert call_count == 1
            
            # Simulate crash
            client._process.returncode = 1
            client.state = ConnectionState.ERROR
            
            # Reconnect should start new process
            result = await client.reconnect()
            assert call_count == 2
            assert result.success is True
            assert client.state == ConnectionState.CONNECTED
    
    def test_config_validation(self):
        """Test stdio client configuration validation."""
        # Valid config
        valid_client = StdioMCPClient(
            name="valid",
            config={
                "command": "npx",
                "args": ["test"],
                "timeout": 30
            }
        )
        assert valid_client.config["command"] == "npx"
        
        # Missing command
        with pytest.raises(ValueError, match="command is required"):
            StdioMCPClient(
                name="invalid",
                config={"args": ["test"]}
            )
        
        # Invalid buffer size
        with pytest.raises(ValueError, match="buffer_size must be positive"):
            StdioMCPClient(
                name="invalid",
                config={
                    "command": "test",
                    "buffer_size": -1
                }
            )
        
        # Invalid working directory
        with pytest.raises(ValueError, match="Working directory .* does not exist"):
            StdioMCPClient(
                name="invalid",
                config={
                    "command": "test",
                    "cwd": "/nonexistent/directory"
                }
            )