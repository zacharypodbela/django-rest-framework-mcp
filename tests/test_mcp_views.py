"""Unit tests for views module."""

import json
import unittest
from unittest.mock import Mock, patch

from django.http import JsonResponse
from django.test import RequestFactory

from djangorestframework_mcp.types import MCPTool
from djangorestframework_mcp.views import MCPView


class TestMCPView(unittest.TestCase):
    """Test the MCPView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = MCPView()

    def test_handle_initialize(self):
        """Test initialize request handling."""
        result = self.view.handle_initialize()

        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("capabilities", result)
        self.assertIn("tools", result["capabilities"])
        self.assertIn("serverInfo", result)
        self.assertEqual(result["serverInfo"]["name"], "django-rest-framework-mcp")
        self.assertEqual(result["serverInfo"]["version"], "0.1.0")

    @patch("djangorestframework_mcp.views.registry")
    @patch("djangorestframework_mcp.views.generate_tool_schema")
    def test_handle_tools_list(self, mock_generate_schema, mock_registry):
        """Test tools/list request handling."""
        # Mock registry response
        mock_tool = MCPTool(
            name="test_tool",
            viewset_class=Mock(),
            action="list",
            description="Test description",
        )
        mock_registry.get_all_tools.return_value = [mock_tool]

        # Mock schema generation
        mock_schema = {
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        }
        mock_generate_schema.return_value = mock_schema

        result = self.view.handle_tools_list()

        self.assertIn("tools", result)
        self.assertEqual(len(result["tools"]), 1)

        tool = result["tools"][0]
        self.assertEqual(tool["name"], "test_tool")
        self.assertEqual(tool["description"], "Test description")
        self.assertEqual(tool["inputSchema"], mock_schema["inputSchema"])

        # Verify calls
        mock_registry.get_all_tools.assert_called_once()
        mock_generate_schema.assert_called_once_with(mock_tool)

    @patch("djangorestframework_mcp.views.registry")
    def test_handle_tools_call_success(self, mock_registry):
        """Test successful tools/call request handling."""
        # Mock tool info
        mock_tool = MCPTool(name="test_tool", viewset_class=Mock(), action="list")
        mock_registry.get_tool_by_name.return_value = mock_tool

        # Mock execute_tool
        mock_result = {"data": [{"id": 1, "name": "test"}]}

        with patch.object(
            self.view, "execute_tool", return_value=mock_result
        ) as mock_execute:
            params = {"name": "test_tool", "arguments": {"param1": "value1"}}

            result = self.view.handle_tools_call(params)

            self.assertIn("content", result)
            self.assertEqual(len(result["content"]), 1)

            content = result["content"][0]
            self.assertEqual(content["type"], "text")

            # The text should be JSON serialized result
            parsed_text = json.loads(content["text"])
            self.assertEqual(parsed_text, mock_result)

            mock_execute.assert_called_once()

    @patch("djangorestframework_mcp.views.registry")
    def test_handle_tools_call_tool_not_found(self, mock_registry):
        """Test tools/call with non-existent tool."""
        mock_registry.get_tool_by_name.return_value = None

        params = {"name": "nonexistent_tool", "arguments": {}}

        result = self.view.handle_tools_call(params)

        self.assertIn("content", result)
        self.assertTrue(result["isError"])

        content = result["content"][0]
        self.assertEqual(content["type"], "text")
        self.assertIn("Tool not found", content["text"])

    @patch("djangorestframework_mcp.views.registry")
    def test_handle_tools_call_execution_error(self, mock_registry):
        """Test tools/call with execution error."""
        mock_tool_info = {"name": "test_tool"}
        mock_registry.get_tool_by_name.return_value = mock_tool_info

        # Mock execute_tool to raise exception
        with patch.object(
            self.view, "execute_tool", side_effect=Exception("Test error")
        ):
            params = {"name": "test_tool", "arguments": {}}

            result = self.view.handle_tools_call(params)

            self.assertIn("content", result)
            self.assertTrue(result["isError"])

            content = result["content"][0]
            self.assertEqual(content["type"], "text")
            self.assertIn("Error executing tool", content["text"])
            self.assertIn("Test error", content["text"])

    def test_error_response(self):
        """Test error response formatting."""
        response = self.view.error_response(123, -32600, "Invalid request")

        self.assertIsInstance(response, JsonResponse)

        # Parse the response content
        content = json.loads(response.content.decode())

        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 123)
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertEqual(content["error"]["message"], "Invalid request")

    def test_error_response_no_id(self):
        """Test error response with no request ID."""
        response = self.view.error_response(None, -32700, "Parse error")

        content = json.loads(response.content.decode())
        self.assertIsNone(content["id"])

    def test_post_initialize_request(self):
        """Test POST request with initialize method."""
        request_data = {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}

        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        response = self.view.post(request)

        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content.decode())

        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("result", content)
        self.assertEqual(content["result"]["protocolVersion"], "2025-06-18")

        # Check that is_mcp_request was set
        self.assertTrue(request.is_mcp_request)

    def test_post_notifications_initialized(self):
        """Test POST request with notifications/initialized method (proper notification)."""
        from django.http import HttpResponse

        request_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            # No 'id' field - this makes it a proper notification
        }

        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        response = self.view.post(request)

        # Per JSON-RPC 2.0, notifications should not return response content
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(response.content), 0)

    def test_post_unknown_method(self):
        """Test POST request with unknown method."""
        request_data = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "params": {},
            "id": 1,
        }

        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        response = self.view.post(request)

        content = json.loads(response.content.decode())
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32601)
        self.assertIn("Method not found", content["error"]["message"])

    def test_post_invalid_json(self):
        """Test POST request with invalid JSON."""
        request = self.factory.post(
            "/mcp/", data="invalid json", content_type="application/json"
        )

        response = self.view.post(request)

        content = json.loads(response.content.decode())
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32700)
        self.assertEqual(content["error"]["message"], "Parse error")

    def test_post_exception_handling(self):
        """Test POST request exception handling."""
        request_data = {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}

        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        # Mock handle_initialize to raise an exception
        with patch.object(
            self.view, "handle_initialize", side_effect=Exception("Test error")
        ):
            response = self.view.post(request)

            content = json.loads(response.content.decode())
            self.assertIn("error", content)
            self.assertEqual(content["error"]["code"], -32603)
            self.assertIn("Internal error", content["error"]["message"])
            self.assertIn("Test error", content["error"]["message"])

    def test_execute_tool(self):
        """Test execute_tool method."""
        # Mock the ViewSet class and action
        mock_viewset_class = Mock()
        mock_viewset_instance = Mock()
        mock_viewset_class.return_value = mock_viewset_instance

        # Mock the required ViewSet methods
        mock_viewset_instance.get_authenticators = Mock(return_value=[])
        mock_viewset_instance.initial = Mock()

        # Mock the action method
        mock_action = Mock(
            return_value=Mock(data={"result": "success"}, status_code=200)
        )
        mock_viewset_instance.list = mock_action

        tool = MCPTool(
            name="test_tool", action="list", viewset_class=mock_viewset_class
        )
        params = {}

        result = self.view.execute_tool(tool, params)

        self.assertEqual(result, {"result": "success"})
        # Check that initial was called (part of the lifecycle)
        mock_viewset_instance.initial.assert_called_once()

        # Verify the action was called with a DRF Request object, not HttpRequest
        mock_action.assert_called_once()
        call_args = mock_action.call_args
        request_arg = call_args[0][0]  # First positional argument
        from rest_framework.request import Request

        self.assertIsInstance(
            request_arg, Request, "Action should receive DRF Request, not HttpRequest"
        )


class TestMCPViewCSRF(unittest.TestCase):
    """Test CSRF handling in MCPView."""

    def test_csrf_exempt_decorator(self):
        """Test that MCPView is properly decorated with csrf_exempt."""
        # Check that the dispatch method has the csrf_exempt marker
        self.assertTrue(hasattr(MCPView.dispatch, "csrf_exempt"))
        # Note: Django's method_decorator applies csrf_exempt to the dispatch method
        # We're checking the decorator was applied rather than testing Django's functionality


class TestMCPViewIntegration(unittest.TestCase):
    """Integration tests for MCPView with mocked components."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = MCPView()

    @patch("djangorestframework_mcp.views.registry")
    @patch("djangorestframework_mcp.views.generate_tool_schema")
    def test_full_tools_list_flow(self, mock_generate_schema, mock_registry):
        """Test complete tools/list request flow."""
        # Set up mocks
        mock_tool = MCPTool(
            name="list_customers",
            description="List customers",
            viewset_class=Mock(),
            action="list",
        )
        mock_registry.get_all_tools.return_value = [mock_tool]

        mock_schema = {
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        }
        mock_generate_schema.return_value = mock_schema

        # Create request
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        # Execute
        response = self.view.post(request)

        # Verify response structure
        content = json.loads(response.content.decode())

        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("result", content)

        result = content["result"]
        self.assertIn("tools", result)
        self.assertEqual(len(result["tools"]), 1)

        tool = result["tools"][0]
        self.assertEqual(tool["name"], "list_customers")
        self.assertEqual(tool["description"], "List customers")
        self.assertEqual(tool["inputSchema"], mock_schema["inputSchema"])


if __name__ == "__main__":
    unittest.main()
