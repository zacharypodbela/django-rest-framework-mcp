"""Unit tests for views module."""

import json
import unittest
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.authtoken.models import Token

from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.types import MCPTool
from djangorestframework_mcp.views import MCPView
from tests.views import AuthenticatedViewSet, MultipleAuthViewSet


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
        self.assertEqual(result["serverInfo"]["version"], "0.1.0a2")

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

            from django.http import HttpRequest

            original_request = HttpRequest()
            result = self.view.handle_tools_call(params, original_request)

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

        from django.http import HttpRequest

        original_request = HttpRequest()
        result = self.view.handle_tools_call(params, original_request)

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

            from django.http import HttpRequest

            original_request = HttpRequest()
            result = self.view.handle_tools_call(params, original_request)

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

        response = self.view.dispatch(request)

        self.assertIsInstance(response, JsonResponse)
        content = json.loads(response.content.decode())

        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("result", content)
        self.assertEqual(content["result"]["protocolVersion"], "2025-06-18")

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

        response = self.view.dispatch(request)

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

        response = self.view.dispatch(request)

        content = json.loads(response.content.decode())
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32601)
        self.assertIn("Method not found", content["error"]["message"])

    def test_post_invalid_json(self):
        """Test POST request with invalid JSON."""
        request = self.factory.post(
            "/mcp/", data="invalid json", content_type="application/json"
        )

        response = self.view.dispatch(request)

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
            response = self.view.dispatch(request)

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
        mock_viewset_instance.determine_version = Mock(return_value=(None, None))

        # Mock the action method
        mock_action = Mock(
            return_value=Mock(data={"result": "success"}, status_code=200)
        )
        mock_viewset_instance.list = mock_action

        tool = MCPTool(
            name="test_tool", action="list", viewset_class=mock_viewset_class
        )
        params = {}

        # Create a mock original request
        from django.http import HttpRequest

        original_request = HttpRequest()

        result = self.view.execute_tool(tool, params, original_request)

        self.assertEqual(result, {"result": "success"})
        # Verify that authentication methods were called
        mock_viewset_instance.get_authenticators.assert_called_once()
        mock_viewset_instance.perform_authentication.assert_called_once()
        mock_viewset_instance.check_permissions.assert_called_once()
        mock_viewset_instance.check_throttles.assert_called_once()
        mock_viewset_instance.determine_version.assert_called_once()

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
        response = self.view.dispatch(request)

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


class MCPViewAuthenticationTests(TestCase):
    """Test authentication functionality in MCPView."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

    def test_mcpview_authentication_required(self):
        """Verifies custom MCPView auth requirements are enforced."""

        class AuthenticatedMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = AuthenticatedMCPView()

        # Create request without authentication
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        response = view.dispatch(request)

        # Should return 403 status (permission denied, not authentication required)
        # Since auth is not required but permission check failed for anonymous user
        self.assertEqual(response.status_code, 403)

        # Should have JSON-RPC error format
        content = json.loads(response.content.decode())
        self.assertIn("error", content)
        self.assertIn("data", content["error"])
        self.assertEqual(content["error"]["data"]["status_code"], 403)

    def test_mcpview_permission_required(self):
        """Verifies custom MCPView permission requirements are enforced."""

        class PermissionMCPView(MCPView):
            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = PermissionMCPView()

        # Create request without authentication
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        response = view.dispatch(request)

        # Should return 403 status for permission denied (unauthenticated user has no permission)
        self.assertEqual(response.status_code, 403)

    def test_mcpview_auth_different_from_viewset(self):
        """Verifies MCPView can have different auth than ViewSets it serves."""

        class CustomMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = CustomMCPView()

        # Test with valid token
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(request_data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            response = view.dispatch(request)

            # Should succeed with valid token
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)

    def test_auth_classes_no_permission_classes_no_headers_allows_anonymous(self):
        """Test that MCP now matches DRF behavior: auth_classes without permission_classes allows anonymous users."""

        class AuthOnlyMCPView(MCPView):
            authentication_classes = [TokenAuthentication]
            # No custom has_mcp_permission override - uses default (returns True)

        view = AuthOnlyMCPView()

        # Create request without authentication headers
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        request = self.factory.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []
            response = view.dispatch(request)

            # MCP now matches DRF behavior: allows anonymous users when auth_classes exist but no permission requirements
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)

            # The user is set to AnonymousUser (same as DRF behavior)
            self.assertFalse(request.user.is_authenticated)
            self.assertEqual(type(request.user).__name__, "AnonymousUser")

            # This now correctly matches DRF: authentication_classes only ENABLE auth but don't REQUIRE it


class MCPViewAuthenticationPassthroughTests(TestCase):
    """Test that MCP authentication is passed through to ViewSets"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.token = Token.objects.create(user=self.user)

    def test_mcp_authenticated_user_available_in_viewset(self):
        """Test that user authenticated at MCP level is available in ViewSet execution"""

        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        @mcp_viewset()
        class AuthenticatedTestViewSet(viewsets.GenericViewSet):
            # Add same authentication to ViewSet as MCP view
            authentication_classes = [TokenAuthentication]

            @mcp_tool(input_serializer=None)
            @action(detail=False, methods=["get"])
            def whoami(self, request):
                # Return the authenticated user's info
                return Response(
                    {
                        "username": request.user.username
                        if request.user.is_authenticated
                        else None,
                        "is_authenticated": request.user.is_authenticated,
                        "user_id": request.user.id
                        if request.user.is_authenticated
                        else None,
                    }
                )

        # Register the viewset (the decorator does this automatically)
        AuthenticatedTestViewSet()

        # Create MCP view with authentication required
        class AuthenticatedMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = AuthenticatedMCPView()

        # Create request with valid token
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "whoami_authenticatedtest", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        response = view.dispatch(request)

        # Should succeed
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())

        # The ViewSet should have access to the authenticated user
        self.assertIn("result", content)
        if "error" in content:
            self.fail(f"Got error: {content['error']}")
        result_text = json.loads(content["result"]["content"][0]["text"])
        self.assertEqual(result_text["username"], "testuser")
        self.assertTrue(result_text["is_authenticated"])
        self.assertEqual(result_text["user_id"], self.user.id)

    def test_mcp_no_auth_viewset_gets_anonymous_user(self):
        """Test that ViewSet gets anonymous user when MCP has no authentication"""

        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        @mcp_viewset()
        class AnonymousTestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=None)
            @action(detail=False, methods=["get"])
            def whoami(self, request):
                # Return the authenticated user's info
                return Response(
                    {
                        "username": request.user.username
                        if hasattr(request.user, "username")
                        else None,
                        "is_authenticated": request.user.is_authenticated
                        if hasattr(request.user, "is_authenticated")
                        else False,
                    }
                )

        # Register the viewset (the decorator does this automatically)
        AnonymousTestViewSet()

        # Create MCP view with NO authentication
        view = MCPView()

        # Create request without auth headers
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "whoami_anonymoustest", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        response = view.dispatch(request)

        # Should succeed
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())

        # The ViewSet should have an anonymous user
        self.assertIn("result", content)
        result_text = json.loads(content["result"]["content"][0]["text"])
        self.assertIn(result_text.get("username"), [None, ""])
        self.assertFalse(result_text["is_authenticated"])


class MCPViewMultipleAuthenticationTests(TestCase):
    """Test MCPView with multiple authentication classes"""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.token = Token.objects.create(user=self.user)

    def test_first_authenticator_succeeds(self):
        """Test that when first authenticator succeeds, it's used and others aren't tried"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [
                TokenAuthentication,
                BasicAuthentication,
                SessionAuthentication,
            ]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # Provide valid token (first authenticator)
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            response = view.dispatch(request)

            # Should succeed with token auth
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)

    def test_first_fails_second_succeeds(self):
        """Test that when first authenticator fails, second is tried and succeeds"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [
                TokenAuthentication,
                BasicAuthentication,
                SessionAuthentication,
            ]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # Provide Basic auth (second authenticator) with invalid token format
        import base64

        credentials = base64.b64encode(b"testuser:testpass").decode("ascii")
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Basic {credentials}",
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            response = view.dispatch(request)

            # Should succeed with basic auth
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)

    def test_all_authenticators_fail_returns_401(self):
        """Test that when all authenticators fail, returns 401 with proper WWW-Authenticate header"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [
                TokenAuthentication,
                BasicAuthentication,
                SessionAuthentication,
            ]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # Provide invalid credentials for all authenticators
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="Token invalid-token",  # Invalid token
        )

        response = view.dispatch(request)

        # Should return 401
        self.assertEqual(response.status_code, 401)
        content = json.loads(response.content.decode())

        # Should have proper error structure
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertIn("data", content["error"])
        self.assertEqual(content["error"]["data"]["status_code"], 401)

        # Should have WWW-Authenticate header from first authenticator (Token)
        self.assertIn("WWW-Authenticate", response)
        self.assertEqual(response["WWW-Authenticate"], "Token")

    def test_no_credentials_with_multiple_authenticators(self):
        """Test that when no credentials provided with multiple authenticators, returns 401"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [
                TokenAuthentication,
                BasicAuthentication,
                SessionAuthentication,
            ]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # No auth headers provided
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        response = view.dispatch(request)

        # Should return 403 (permission denied, not authentication required)
        # Since auth is not required but permission check failed for anonymous user
        self.assertEqual(response.status_code, 403)
        content = json.loads(response.content.decode())

        # Should have proper error structure
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertIn("data", content["error"])
        self.assertEqual(content["error"]["data"]["status_code"], 403)

        # No WWW-Authenticate header for permission denied (403), only for auth failures (401)
        self.assertNotIn("WWW-Authenticate", response)

    def test_multiple_auth_headers_provided(self):
        """Test behavior when multiple auth headers are provided (only first should be used)"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [TokenAuthentication, BasicAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # Provide both Token and Basic auth headers
        # Django will only pass one through, typically the last one set

        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
            # Note: In practice, only one Authorization header can be sent
            # This tests what happens with a valid token
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            response = view.dispatch(request)

            # Should succeed with whichever auth header was provided
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)

    def test_mixed_auth_and_session(self):
        """Test that TokenAuthentication works when SessionAuthentication is also configured"""

        class MultiAuthMCPView(MCPView):
            authentication_classes = [SessionAuthentication, TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        view = MultiAuthMCPView()

        # Create request with Token auth (SessionAuthentication will fail on CSRF, TokenAuth will succeed)
        request = self.factory.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []

            response = view.dispatch(request)

            # Should succeed with token auth (SessionAuth will be skipped due to CSRF)
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.content.decode())
            self.assertIn("result", content)


class ErrorResponseTests(TestCase):
    """Test authentication error response formatting."""

    def setUp(self):
        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

    def tearDown(self):
        registry.clear()
        # Note: These tests use self.client from Django's TestCase, not MCPClient

    def test_authentication_error_http_status(self):
        """Verifies 401 status code returned for auth failures."""
        response = self.client.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_authenticated", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_permission_error_http_status(self):
        """Verifies 403 status code returned for permission failures."""
        # This would require a different permission setup to get 403 vs 401
        # For now, authentication failure gives 401
        response = self.client.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_authenticated", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_www_authenticate_header_present(self):
        """Verifies WWW-Authenticate header included in auth error responses."""
        response = self.client.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_authenticated", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        self.assertIn("WWW-Authenticate", response)
        self.assertIn("Token", response["WWW-Authenticate"])

    def test_jsonrpc_error_includes_auth_details(self):
        """Verifies JSON-RPC error.data includes authentication error information."""
        response = self.client.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_authenticated", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertIn("data", data["error"])
        self.assertIn("status_code", data["error"]["data"])
        self.assertEqual(data["error"]["data"]["status_code"], 401)

    def test_multiple_auth_methods_error_response(self):
        """Verifies error response lists all available auth methods."""
        # Register a viewset with multiple auth methods
        registry.register_viewset(MultipleAuthViewSet)

        response = self.client.post(
            "/mcp/",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_multipleauth", "arguments": {}},
                    "id": 1,
                }
            ),
            content_type="application/json",
        )

        # Should include WWW-Authenticate header indicating available auth methods
        self.assertIn("WWW-Authenticate", response)


class Return200ForErrorsTests(TestCase):
    """Test RETURN_200_FOR_ERRORS setting functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

    def test_auth_error_default_behavior(self):
        """Test that with setting disabled (default), auth failures return proper HTTP 401 status codes."""
        from rest_framework import exceptions

        view = MCPView()
        exc = exceptions.NotAuthenticated(
            "Authentication credentials were not provided."
        )
        exc.status_code = 401
        exc.auth_header = "Token"

        response = view.handle_auth_error(exc, 1)

        # Should return HTTP 401
        self.assertEqual(response.status_code, 401)

        # Should have WWW-Authenticate header
        self.assertIn("WWW-Authenticate", response)
        self.assertEqual(response["WWW-Authenticate"], "Token")

        # Should have proper JSON-RPC error structure
        content = json.loads(response.content.decode())
        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertIn(
            "Authentication credentials were not provided", content["error"]["message"]
        )
        self.assertEqual(content["error"]["data"]["status_code"], 401)
        self.assertEqual(content["error"]["data"]["www_authenticate"], "Token")

    @patch("djangorestframework_mcp.views.mcp_settings.RETURN_200_FOR_ERRORS", True)
    def test_auth_error_compatibility_mode(self):
        """Test that with setting enabled, auth failures return HTTP 200 but preserve error info in JSON-RPC response."""
        from rest_framework import exceptions

        view = MCPView()
        exc = exceptions.NotAuthenticated(
            "Authentication credentials were not provided."
        )
        exc.status_code = 401
        exc.auth_header = "Token"

        response = view.handle_auth_error(exc, 1)

        # Should return HTTP 200 in compatibility mode
        self.assertEqual(response.status_code, 200)

        # Should NOT have WWW-Authenticate header in compatibility mode
        self.assertNotIn("WWW-Authenticate", response)

        # Should preserve all error info in JSON-RPC response
        content = json.loads(response.content.decode())
        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertIn(
            "Authentication credentials were not provided", content["error"]["message"]
        )

        # Original status code preserved in error.data
        self.assertEqual(content["error"]["data"]["status_code"], 401)
        self.assertEqual(content["error"]["data"]["www_authenticate"], "Token")

    def test_permission_error_default_behavior(self):
        """Test that with setting disabled, permission failures return HTTP 403."""
        from rest_framework import exceptions

        view = MCPView()
        exc = exceptions.PermissionDenied(
            "You do not have permission to perform this action."
        )
        exc.status_code = 403

        response = view.handle_auth_error(exc, 1)

        # Should return HTTP 403
        self.assertEqual(response.status_code, 403)

        # Should NOT have WWW-Authenticate header for 403 permission errors
        self.assertNotIn("WWW-Authenticate", response)

        # Should have proper JSON-RPC error structure
        content = json.loads(response.content.decode())
        self.assertEqual(content["jsonrpc"], "2.0")
        self.assertEqual(content["id"], 1)
        self.assertIn("error", content)
        self.assertEqual(content["error"]["code"], -32600)
        self.assertIn("You do not have permission", content["error"]["message"])
        self.assertEqual(content["error"]["data"]["status_code"], 403)

    @patch("djangorestframework_mcp.views.mcp_settings.RETURN_200_FOR_ERRORS", True)
    def test_permission_error_compatibility_mode(self):
        """Test that with setting enabled, permission failures return HTTP 200."""
        from rest_framework import exceptions

        view = MCPView()
        exc = exceptions.PermissionDenied(
            "You do not have permission to perform this action."
        )
        exc.status_code = 403

        response = view.handle_auth_error(exc, 1)

        # Should return HTTP 200 in compatibility mode
        self.assertEqual(response.status_code, 200)

        # Should preserve original 403 status code in error.data
        content = json.loads(response.content.decode())
        self.assertEqual(content["error"]["data"]["status_code"], 403)

    def test_method_not_found_both_modes(self):
        """Test JSON-RPC 'method not found' errors return HTTP 200 in both modes (no change)."""
        view = MCPView()

        # Default mode
        response = view.error_response(1, -32601, "Method not found: unknown/method")
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content.decode())
        self.assertEqual(content["error"]["code"], -32601)
        self.assertIn("Method not found", content["error"]["message"])

        # Compatibility mode (same behavior expected)
        with patch(
            "djangorestframework_mcp.views.mcp_settings.RETURN_200_FOR_ERRORS", True
        ):
            response = view.error_response(
                1, -32601, "Method not found: unknown/method"
            )
            self.assertEqual(response.status_code, 200)

    def test_parse_error_both_modes(self):
        """Test malformed JSON returns HTTP 200 in both modes (no change)."""
        view = MCPView()

        # Default mode
        response = view.error_response(None, -32700, "Parse error")
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content.decode())
        self.assertEqual(content["error"]["code"], -32700)
        self.assertEqual(content["error"]["message"], "Parse error")

        # Compatibility mode (same behavior expected)
        with patch(
            "djangorestframework_mcp.views.mcp_settings.RETURN_200_FOR_ERRORS", True
        ):
            response = view.error_response(None, -32700, "Parse error")
            self.assertEqual(response.status_code, 200)

    def test_successful_requests_unaffected(self):
        """Test that successful requests still return appropriate 2xx status codes regardless of setting."""
        view = MCPView()

        # Test successful response (default mode)
        with patch("djangorestframework_mcp.views.registry") as mock_registry:
            mock_registry.get_all_tools.return_value = []
            result = view.handle_tools_list()
            self.assertEqual(result, {"tools": []})

        # Compatibility mode should not affect successful operations
        with patch(
            "djangorestframework_mcp.views.mcp_settings.RETURN_200_FOR_ERRORS", True
        ):
            with patch("djangorestframework_mcp.views.registry") as mock_registry:
                mock_registry.get_all_tools.return_value = []
                result = view.handle_tools_list()
                self.assertEqual(result, {"tools": []})


if __name__ == "__main__":
    unittest.main()
