"""Unit tests for test utilities module."""

import json
import unittest
from unittest.mock import Mock, patch

from django.test import Client

from djangorestframework_mcp.test import MCPClient


class TestMCPClient(unittest.TestCase):
    """Test the MCPClient utility class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create client without auto-initialization to test manually
        self.client = MCPClient(auto_initialize=False)

    def test_initialization(self):
        """Test MCPClient initialization."""
        # Test manual initialization
        self.assertFalse(self.client._initialized)
        self.assertEqual(self.client.mcp_endpoint, "/mcp/")

    def test_auto_initialization(self):
        """Test MCPClient auto-initialization."""
        with patch.object(MCPClient, "initialize"):
            auto_client = MCPClient(auto_initialize=True)
            auto_client.initialize.assert_called_once()

    def test_call_tool_success(self):
        """Test successful tool call."""
        # Mock response with proper MCP format
        mock_response = Mock()
        response_data = {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": '{"data": "result"}'}],
                "structuredContent": {"data": "result"},
            },
            "id": 1,
        }
        mock_response.content = json.dumps(response_data).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response):
            result = self.client.call_tool("test_tool", {"param": "value"})

            self.assertEqual(result["structuredContent"], {"data": "result"})

    def test_call_tool_with_protocol_error(self):
        """Test tool call with MCP protocol error (should raise)."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid request"},
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.client.call_tool("test_tool")

            self.assertIn("MCP protocol error -32600", str(context.exception))
            self.assertIn("Invalid request", str(context.exception))

    def test_call_tool_with_execution_error(self):
        """Test tool call with tool execution error (should return as data)."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": "Tool execution failed"}],
                    "isError": True,
                },
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response):
            result = self.client.call_tool("test_tool")

            # Tool execution errors are returned as data, not raised
            self.assertTrue(result.get("isError"))
            self.assertEqual(result["content"][0]["text"], "Tool execution failed")

    def test_call_tool_request_structure(self):
        """Test that call_tool creates proper JSON-RPC request."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": "{}"}],
                    "structuredContent": {},
                },
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response) as mock_post:
            self.client.call_tool("test_tool", {"param1": "value1", "param2": 42})

            # Verify the POST call
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check URL (first positional argument)
            self.assertEqual(call_args[0][0], "/mcp/")

            # Check content type
            self.assertEqual(call_args[1]["content_type"], "application/json")

            # Parse and check the request data
            request_data = json.loads(call_args[1]["data"])

            self.assertEqual(request_data["jsonrpc"], "2.0")
            self.assertEqual(request_data["method"], "tools/call")
            self.assertEqual(request_data["id"], 1)

            params = request_data["params"]
            self.assertEqual(params["name"], "test_tool")
            self.assertEqual(params["arguments"], {"param1": "value1", "param2": 42})

    def test_call_tool_no_params(self):
        """Test call_tool with no parameters."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": "{}"}],
                    "structuredContent": {},
                },
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response) as mock_post:
            self.client.call_tool("test_tool")

            # Check that arguments is empty dict
            request_data = json.loads(mock_post.call_args[1]["data"])
            self.assertEqual(request_data["params"]["arguments"], {})

    def test_call_tool_uninitialized(self):
        """Test call_tool raises when client not initialized."""
        # Client is not initialized
        with self.assertRaises(RuntimeError) as context:
            self.client.call_tool("test_tool")

        self.assertIn("must complete initialization", str(context.exception))

    def test_list_tools_success(self):
        """Test successful tools listing."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {
                            "name": "tool1",
                            "description": "Test tool 1",
                            "inputSchema": {"type": "object"},
                        },
                        {
                            "name": "tool2",
                            "description": "Test tool 2",
                            "inputSchema": {"type": "object"},
                        },
                    ]
                },
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response):
            result = self.client.list_tools()

            tools = result["tools"]
            self.assertEqual(len(tools), 2)
            self.assertEqual(tools[0]["name"], "tool1")
            self.assertEqual(tools[1]["name"], "tool2")

    def test_list_tools_request_structure(self):
        """Test that list_tools creates proper JSON-RPC request."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {"jsonrpc": "2.0", "result": {"tools": []}, "id": 1}
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response) as mock_post:
            self.client.list_tools()

            # Verify the POST call
            mock_post.assert_called_once()
            call_args = mock_post.call_args

            # Check URL (first positional argument) and content type
            self.assertEqual(call_args[0][0], "/mcp/")
            self.assertEqual(call_args[1]["content_type"], "application/json")

            # Parse and check the request data
            request_data = json.loads(call_args[1]["data"])

            self.assertEqual(request_data["jsonrpc"], "2.0")
            self.assertEqual(request_data["method"], "tools/list")
            self.assertEqual(request_data["params"], {})
            self.assertEqual(request_data["id"], 1)

    def test_list_tools_with_error(self):
        """Test list_tools with MCP protocol error."""
        mock_response = Mock()
        mock_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "Internal error"},
                "id": 1,
            }
        ).encode()

        # Set client as initialized and mock the post method
        self.client._initialized = True
        with patch.object(self.client, "post", return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.client.list_tools()

            self.assertIn("MCP protocol error -32603", str(context.exception))
            self.assertIn("Internal error", str(context.exception))

    def test_initialize_method(self):
        """Test the initialize method."""
        # Mock successful initialization responses
        init_response = Mock()
        init_response.content = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                },
                "id": "init",
            }
        ).encode()

        notification_response = Mock()
        notification_response.content = b""

        with patch.object(
            self.client, "post", side_effect=[init_response, notification_response]
        ) as mock_post:
            result = self.client.initialize()

            # Should be marked as initialized
            self.assertTrue(self.client._initialized)

            # Should return the initialization result
            self.assertEqual(result["protocolVersion"], "0.1.0")

            # Should have made two POST calls (init + notification)
            self.assertEqual(mock_post.call_count, 2)


class TestMCPClientIntegration(unittest.TestCase):
    """Integration tests for MCPClient."""

    def test_inheritance(self):
        """Test that MCPClient properly inherits from Django Client."""
        self.assertTrue(issubclass(MCPClient, Client))

    def test_docstring_and_methods(self):
        """Test MCPClient has proper documentation and methods."""
        self.assertIsNotNone(MCPClient.__doc__)

        # Check required methods exist
        self.assertTrue(hasattr(MCPClient, "call_tool"))
        self.assertTrue(hasattr(MCPClient, "list_tools"))
        self.assertTrue(hasattr(MCPClient, "initialize"))

        # Check methods are callable
        self.assertTrue(callable(MCPClient.call_tool))
        self.assertTrue(callable(MCPClient.list_tools))
        self.assertTrue(callable(MCPClient.initialize))


if __name__ == "__main__":
    unittest.main()
