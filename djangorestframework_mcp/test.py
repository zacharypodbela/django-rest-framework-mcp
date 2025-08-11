"""Test utilities for MCP tools following Django REST Framework patterns.

This module provides an MCP test client that extends Django's Client,
properly encapsulating MCP protocol concerns while remaining familiar
to Django developers.
"""

import json
from typing import Any, Dict, Optional

from django.test import Client


class MCPClient(Client):
    """Test client for interacting with MCP servers.

    Extends Django's test Client to handle MCP protocol communication,
    including proper initialization handshake and JSON-RPC message formatting.
    This separation of protocol concerns from test logic follows the same
    pattern as DRF's APIClient.

    Attributes:
        mcp_endpoint: The server endpoint path for MCP communication.

    Example:
        class MyMCPTests(TestCase):
            def test_my_tool(self):
                client = MCPClient()
                result = client.call_tool('my_tool', {'param': 'value'})
                self.assertFalse(result.get('isError'))
                data = result['structuredContent']
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]['name'], 'Active Customer')
    """

    def __init__(self, *args, mcp_endpoint="mcp/", auto_initialize=True, **kwargs):
        """Initialize the MCP test client.

        Args:
            mcp_endpoint: The URL path to the MCP server endpoint.
                         Defaults to 'mcp/' to match the library's default routing.
            auto_initialize: Whether to automatically perform the MCP initialization
                           handshake. Set to False if you need to test initialization
                           behavior explicitly. Defaults to True.
            *args / **kwargs: Additional arguments passed to Django's Client constructor.
                            (See signature of django.test.Client for list of valid arguments)
        """
        super().__init__(*args, **kwargs)
        self.mcp_endpoint = "/" + mcp_endpoint.lstrip("/")
        self._initialized = False

        if auto_initialize:
            self.initialize()

    def initialize(self) -> Dict[str, Any]:
        """Perform the MCP initialization handshake with the server.

        Sends an 'initialize' request per the MCP protocol specification,
        establishing the connection and discovering server capabilities.

        Returns:
            The server's initialization response containing protocol version
            and capabilities.

        Raises:
            Exception: If the initialization request fails.
        """
        request_data = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "djangorestframework-mcp-test-client",
                    "version": "0.1.0",
                },
            },
            "id": "init",
        }

        response = self.post(
            self.mcp_endpoint,
            data=json.dumps(request_data),
            content_type="application/json",
        )

        response_data = json.loads(response.content)

        if "error" in response_data:
            raise Exception(f"MCP initialization failed: {response_data['error']}")

        notification_data = {"jsonrpc": "2.0", "method": "notifications/initialized"}

        self.post(
            self.mcp_endpoint,
            data=json.dumps(notification_data),
            content_type="application/json",
        )

        self._initialized = True
        return response_data.get("result", {})

    def _raise_if_uninitialized(self):
        """Verify the client has completed initialization.

        Internal method to enforce MCP protocol requirements that all
        requests must occur after successful initialization.

        Raises:
            RuntimeError: If initialize() has not been called successfully.
        """
        if not self._initialized:
            raise RuntimeError(
                "MCP client must complete initialization handshake before making requests. "
                "Call initialize() first or use auto_initialize=True."
            )

    def _raise_protocol_errors(self, response_data: Dict[str, Any]) -> None:
        """Check for protocol errors and raise if found.

        Protocol errors indicate bugs in the library or setup that should
        be fixed rather than tested.

        Args:
            response_data: The parsed JSON-RPC response.

        Raises:
            Exception: If the response contains a protocol error.
        """
        if "error" in response_data:
            error = response_data["error"]
            raise Exception(f"MCP protocol error {error['code']}: {error['message']}")

    def call_tool(
        self, tool_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute an MCP tool with the specified arguments.

        Sends a 'tools/call' request following the MCP protocol. Returns
        the tool result, raising exceptions only for protocol-level errors.

        Args:
            tool_name: The registered name of the MCP tool to execute.
            arguments: Tool-specific parameters as a dictionary.

        Returns:
            The MCP tool result. Tool execution errors (validation failures,
            business logic errors, etc.) are returned as data with isError: true.

        Raises:
            RuntimeError: If the client hasn't been initialized.
            Exception: For JSON-RPC protocol errors (bugs in library/setup).

        Example:
            client = MCPClient()
            result = client.call_tool('customers_list')

            # Check for tool execution errors (testable scenarios)
            if result.get('isError'):
                error_text = result['content'][0]['text']
                self.assertIn('validation', error_text)
            else:
                # Access successful result via structured content
                data = result['structuredContent']
                self.assertEqual(len(data), 2)
                self.assertEqual(data[0]['name'], 'Alice')
        """
        self._raise_if_uninitialized()

        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
            "id": 1,
        }

        response = self.post(
            self.mcp_endpoint,
            data=json.dumps(request_data),
            content_type="application/json",
        )

        response_data = json.loads(response.content)
        self._raise_protocol_errors(response_data)

        return response_data["result"]

    def list_tools(self) -> Dict[str, Any]:
        """Discover all available MCP tools from the server.

        Sends a 'tools/list' request and returns the result.

        Returns:
            The tools/list result containing the 'tools' array.

        Raises:
            RuntimeError: If the client hasn't been initialized.
            Exception: For JSON-RPC protocol errors (bugs in library/setup).

        Example:
            client = MCPClient()
            result = client.list_tools()

            # Access tools directly
            tools = result['tools']
            for tool in tools:
                print(f"{tool['name']}: {tool['description']}")
        """
        self._raise_if_uninitialized()

        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        response = self.post(
            self.mcp_endpoint,
            data=json.dumps(request_data),
            content_type="application/json",
        )

        response_data = json.loads(response.content)
        self._raise_protocol_errors(response_data)

        return response_data["result"]
