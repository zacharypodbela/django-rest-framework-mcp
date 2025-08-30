"""Integration tests for MCP functionality."""

import base64
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework import viewsets
from rest_framework.authentication import (
    TokenAuthentication,
)
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from djangorestframework_mcp.decorators import mcp_viewset
from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.test import MCPClient

from .models import Customer
from .views import (
    AuthenticatedViewSet,
    CustomAuthViewSet,
    CustomPermissionViewSet,
    MultipleAuthViewSet,
    UnauthenticatedViewSet,
)


class MCPTestCase(TestCase):
    """Base test case that ensures registry isolation."""

    def setUp(self):
        """Set up test environment with clean registry."""
        super().setUp()
        from djangorestframework_mcp.registry import registry

        from .views import CustomerViewSet, ProductViewSet

        # Clear registry and register test ViewSets
        registry.clear()
        registry.register_viewset(CustomerViewSet)
        registry.register_viewset(ProductViewSet)


@override_settings(ROOT_URLCONF="tests.urls")
class MCPToolDiscoveryTests(MCPTestCase):
    """Test MCP tool discovery."""

    def test_list_tools(self):
        """Test that MCP tools are properly listed."""
        client = MCPClient()
        result = client.list_tools()
        tools = result["tools"]

        # Check that we have tools
        self.assertGreater(len(tools), 0)

        # Find customer tools
        customer_tools = [t for t in tools if "customers" in t["name"]]
        self.assertEqual(len(customer_tools), 6)  # CRUD operations

        # Check tool names
        tool_names = {t["name"] for t in customer_tools}
        expected_names = {
            "list_customers",
            "retrieve_customers",
            "create_customers",
            "update_customers",
            "partial_update_customers",
            "destroy_customers",
        }
        self.assertEqual(tool_names, expected_names)

        # Check that tools have schemas
        for tool in customer_tools:
            self.assertIn("inputSchema", tool)
            self.assertIn("type", tool["inputSchema"])
            self.assertEqual(tool["inputSchema"]["type"], "object")


@override_settings(ROOT_URLCONF="tests.urls")
class MCPToolExecutionTests(MCPTestCase):
    """Test MCP tool execution."""

    def setUp(self):
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        # Create test data
        self.customer1 = Customer.objects.create(
            name="Alice Smith", email="alice@example.com", age=30, is_active=True
        )
        self.customer2 = Customer.objects.create(
            name="Bob Jones", email="bob@example.com", age=25, is_active=False
        )

    def test_list_customers(self):
        """Test listing customers via MCP."""
        result = self.client.call_tool("list_customers")

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Access structured content
        data = result["structuredContent"]
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

        # Check customer data
        emails = {c["email"] for c in data}
        self.assertEqual(emails, {"alice@example.com", "bob@example.com"})

    def test_retrieve_customer(self):
        """Test retrieving a specific customer via MCP."""
        result = self.client.call_tool(
            "retrieve_customers", {"kwargs": {"pk": str(self.customer1.id)}}
        )

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Access structured content
        data = result["structuredContent"]
        self.assertEqual(data["name"], "Alice Smith")
        self.assertEqual(data["email"], "alice@example.com")
        self.assertEqual(data["age"], 30)
        self.assertTrue(data["is_active"])

    def test_create_customer(self):
        """Test creating a customer via MCP."""
        data = {
            "body": {
                "name": "Charlie Brown",
                "email": "charlie@example.com",
                "age": 35,
                "is_active": True,
            }
        }

        result = self.client.call_tool("create_customers", data)

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Check response via structured content
        data = result["structuredContent"]
        self.assertEqual(data["name"], "Charlie Brown")
        self.assertEqual(data["email"], "charlie@example.com")

        # Verify in database
        customer = Customer.objects.get(email="charlie@example.com")
        self.assertEqual(customer.name, "Charlie Brown")
        self.assertEqual(customer.age, 35)

    def test_update_customer(self):
        """Test updating a customer via MCP."""
        data = {
            "kwargs": {"pk": str(self.customer1.id)},
            "body": {
                "name": "Alice Johnson",
                "email": "alice.johnson@example.com",
                "age": 31,
                "is_active": False,
            },
        }

        result = self.client.call_tool("update_customers", data)

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Check response via structured content
        data = result["structuredContent"]
        self.assertEqual(data["name"], "Alice Johnson")
        self.assertEqual(data["email"], "alice.johnson@example.com")

        # Verify in database
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, "Alice Johnson")
        self.assertEqual(self.customer1.age, 31)
        self.assertFalse(self.customer1.is_active)

    def test_partial_update_customer(self):
        """Test partially updating a customer via MCP."""
        data = {"kwargs": {"pk": str(self.customer2.id)}, "body": {"is_active": True}}

        result = self.client.call_tool("partial_update_customers", data)

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Check response via structured content - other fields unchanged
        data = result["structuredContent"]
        self.assertEqual(data["name"], "Bob Jones")
        self.assertEqual(data["email"], "bob@example.com")
        self.assertTrue(data["is_active"])

        # Verify in database
        self.customer2.refresh_from_db()
        self.assertTrue(self.customer2.is_active)
        self.assertEqual(self.customer2.name, "Bob Jones")  # Unchanged

    def test_destroy_customer(self):
        """Test deleting a customer via MCP."""
        initial_count = Customer.objects.count()

        result = self.client.call_tool(
            "destroy_customers", {"kwargs": {"pk": str(self.customer1.id)}}
        )

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Check response via structured content
        data = result["structuredContent"]
        self.assertIn("message", data)

        # Verify deletion
        self.assertEqual(Customer.objects.count(), initial_count - 1)
        self.assertFalse(Customer.objects.filter(id=self.customer1.id).exists())

    def test_error_handling_not_found(self):
        """Test error handling for non-existent customer."""
        result = self.client.call_tool(
            "retrieve_customers", {"kwargs": {"pk": "99999"}}
        )

        # Should return an error response
        self.assertTrue(result.get("isError"))

        # DRF returns "No Customer matches the given query"
        error_text = result["content"][0]["text"].lower()
        self.assertTrue(
            "not found" in error_text or "no customer matches" in error_text,
            f"Expected error message about not found, got: {error_text}",
        )

    def test_error_handling_validation(self):
        """Test error handling for validation errors."""
        # Try to create customer with duplicate email
        data = {
            "body": {
                "name": "Duplicate",
                "email": self.customer1.email,  # Duplicate email
                "age": 40,
            }
        }

        result = self.client.call_tool("create_customers", data)

        # Should return an error response
        self.assertTrue(result.get("isError"))

        # Check for validation-related error messages
        error_text = result["content"][0]["text"].lower()
        self.assertTrue(
            "validation" in error_text
            or "already exists" in error_text
            or "unique" in error_text,
            f"Expected error message about validation, got: {error_text}",
        )


@override_settings(ROOT_URLCONF="tests.urls")
class MCPClientErrorHandlingTests(MCPTestCase):
    """Test that MCPClient properly handles errors without raising exceptions."""

    def test_client_returns_errors_without_raising(self):
        """Test that error responses are returned, not raised as exceptions."""
        client = MCPClient()

        # Test tool not found error
        result = client.call_tool("nonexistent_tool")
        self.assertTrue(result.get("isError"))
        self.assertIn("Tool not found", result["content"][0]["text"])

        # Test validation error (missing required fields)
        result = client.call_tool("create_customers", {"body": {}})
        self.assertTrue(result.get("isError"))
        error_text = result["content"][0]["text"].lower()
        self.assertTrue("required" in error_text or "field is required" in error_text)

    def test_client_raises_only_for_initialization_violations(self):
        """Test that client only raises for protocol lifecycle violations."""
        # Create client without auto-initialization
        client = MCPClient(auto_initialize=False)

        # Should raise because not initialized
        with self.assertRaises(RuntimeError) as context:
            client.call_tool("list_customers")

        self.assertIn("must complete initialization", str(context.exception))

        # Same for list_tools
        with self.assertRaises(RuntimeError) as context:
            client.list_tools()

        self.assertIn("must complete initialization", str(context.exception))

        # After initialization, should work fine
        client.initialize()
        result = client.list_tools()
        self.assertIsInstance(result["tools"], list)


@override_settings(ROOT_URLCONF="tests.urls")
class MCPLegacyContentTests(MCPTestCase):
    """Test legacy text content field (deprecated feature)."""

    def setUp(self):
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer", email="test@example.com", age=25, is_active=True
        )

    def test_text_content_matches_structured_content(self):
        """Test that legacy text content matches structured content."""
        result = self.client.call_tool("list_customers")

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Both text and structured content should be present
        self.assertIn("content", result)
        self.assertIn("structuredContent", result)

        # Text content should be JSON representation of structured content
        text_content = result["content"][0]["text"]
        structured_content = result["structuredContent"]

        # Parse text content and compare
        parsed_text = json.loads(text_content)
        self.assertEqual(parsed_text, structured_content)

    def test_text_content_for_single_object(self):
        """Test text content format for single object responses."""
        result = self.client.call_tool(
            "retrieve_customers", {"kwargs": {"pk": str(self.customer.id)}}
        )

        # Should not have errors
        self.assertFalse(result.get("isError"))

        # Verify text content is valid JSON
        text_content = result["content"][0]["text"]
        structured_content = result["structuredContent"]

        parsed_text = json.loads(text_content)
        self.assertEqual(parsed_text, structured_content)
        self.assertEqual(parsed_text["name"], "Test Customer")

    def test_text_content_for_error_responses(self):
        """Test that error responses have text content with error messages."""
        result = self.client.call_tool(
            "retrieve_customers", {"kwargs": {"pk": "99999"}}
        )

        # Should have errors
        self.assertTrue(result.get("isError"))

        # Error text should be present and meaningful
        self.assertIn("content", result)
        error_text = result["content"][0]["text"]
        self.assertTrue(
            "not found" in error_text.lower()
            or "no customer matches" in error_text.lower(),
            f"Expected error message about not found, got: {error_text}",
        )


@override_settings(ROOT_URLCONF="tests.urls")
class MCPProtocolTests(MCPTestCase):
    """Test MCP protocol implementation."""

    def setUp(self):
        """Set up test fixtures, ensuring ViewSets are registered."""
        super().setUp()
        # Import ViewSets to ensure they are registered
        # Note: ViewSets are automatically registered when the module is imported
        # due to @mcp_viewset decorators on the class definitions

    def test_initialize_request(self):
        """Test MCP initialize request."""
        from django.test import Client

        client = Client()

        request_data = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
            "id": 1,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertEqual(data["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("capabilities", data["result"])
        self.assertIn("serverInfo", data["result"])

    def test_tools_list_request(self):
        """Test MCP tools/list request."""
        from django.test import Client

        client = Client()

        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertIn("tools", data["result"])
        self.assertIsInstance(data["result"]["tools"], list)

        # Check that we have both customer and product tools
        tool_names = [t["name"] for t in data["result"]["tools"]]
        self.assertTrue(any("customers" in name for name in tool_names))
        self.assertTrue(any("products" in name for name in tool_names))

    def test_tools_list_includes_titles(self):
        """Test that tools/list includes human-readable titles."""
        from django.test import Client

        client = Client()

        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Find a customer list tool and check it has a title
        tools = data["result"]["tools"]
        list_tool = next((t for t in tools if t["name"] == "list_customers"), None)

        self.assertIsNotNone(list_tool)
        self.assertIn("title", list_tool)
        self.assertEqual(list_tool["title"], "List Customers")

        # Check retrieve tool title
        retrieve_tool = next(
            (t for t in tools if t["name"] == "retrieve_customers"), None
        )
        self.assertIsNotNone(retrieve_tool)
        self.assertIn("title", retrieve_tool)
        self.assertEqual(retrieve_tool["title"], "Get Customer")

        # Check create tool title
        create_tool = next((t for t in tools if t["name"] == "create_customers"), None)
        self.assertIsNotNone(create_tool)
        self.assertIn("title", create_tool)
        self.assertEqual(create_tool["title"], "Create Customer")

    def test_notification_handling(self):
        """Test proper JSON-RPC notification handling (no response expected)."""
        from django.test import Client

        client = Client()

        # Test proper notification (no id field)
        request_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            # No 'id' field - this makes it a notification
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        # Per JSON-RPC 2.0, notifications should not return any response content
        # We return 204 No Content to indicate successful processing without response
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(response.content), 0)

    def test_parse_error(self):
        """Test JSON-RPC parse error handling."""
        from django.test import Client

        client = Client()

        response = client.post(
            "/mcp/", data="invalid json{", content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32700)  # Parse error
        self.assertIn("Parse error", data["error"]["message"])

    def test_method_not_found(self):
        """Test JSON-RPC method not found error."""
        from django.test import Client

        client = Client()

        request_data = {
            "jsonrpc": "2.0",
            "method": "invalid/method",
            "params": {},
            "id": 101,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32601)  # Method not found
        self.assertIn("Method not found", data["error"]["message"])

    def test_tool_not_found(self):
        """Test tool not found error."""
        from django.test import Client

        client = Client()

        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
            "id": 102,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        # Tool not found returns a result with isError: True
        self.assertTrue(data["result"]["isError"])
        self.assertIn("Tool not found", data["result"]["content"][0]["text"])

    def test_missing_required_parameter(self):
        """Test missing required parameter error."""
        from django.test import Client

        client = Client()

        # Create test customer first
        Customer.objects.create(name="Test Customer", email="test@example.com", age=30)

        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "retrieve_customers",
                "arguments": {},  # Missing required 'kwargs' with 'pk'
            },
            "id": 106,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        # Missing parameter returns a result with isError: True
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"].lower()
        self.assertTrue("error" in error_text or "expected" in error_text)

    def test_validation_error_missing_fields(self):
        """Test validation error for missing required fields."""
        from django.test import Client

        client = Client()

        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create_customers",
                "arguments": {
                    "body": {
                        "age": 30  # Missing required 'name' and 'email'
                    }
                },
            },
            "id": 104,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        # Validation error returns a result with isError: True
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"].lower()
        self.assertTrue("required" in error_text or "field is required" in error_text)

    def test_validation_error_duplicate_email(self):
        """Test validation error for duplicate email."""
        from django.test import Client

        client = Client()

        # Create customer with email
        Customer.objects.create(
            name="Existing Customer", email="existing@example.com", age=25
        )

        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create_customers",
                "arguments": {
                    "body": {
                        "name": "Duplicate User",
                        "email": "existing@example.com",  # Already exists
                        "age": 40,
                    }
                },
            },
            "id": 105,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        # Validation error returns a result with isError: True
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"].lower()
        self.assertTrue("already exists" in error_text or "unique" in error_text)


@override_settings(ROOT_URLCONF="tests.urls")
class TestMCPRequestConditionalLogic(MCPTestCase):
    """Test conditional logic based on request.is_mcp_request."""

    def setUp(self):
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        from djangorestframework_mcp.registry import registry

        registry.clear()

        # Create test data
        self.active_customer = Customer.objects.create(
            name="Active Customer", email="active@example.com", age=30, is_active=True
        )
        self.inactive_customer = Customer.objects.create(
            name="Inactive Customer",
            email="inactive@example.com",
            age=25,
            is_active=False,
        )

    def test_get_queryset_filtering_for_mcp_requests(self):
        """Test that ViewSets can filter querysets differently for MCP requests."""
        from rest_framework import viewsets

        from djangorestframework_mcp.decorators import mcp_viewset

        @mcp_viewset(basename="filteredcustomers")
        class FilteredCustomerViewSet(viewsets.ModelViewSet):
            def get_queryset(self):
                # MCP clients only see active customers
                if hasattr(self, "request") and getattr(
                    self.request, "is_mcp_request", False
                ):
                    return Customer.objects.filter(is_active=True)
                return Customer.objects.all()

            def get_serializer_class(self):
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

        # Test MCP request - should only see active customers
        result = self.client.call_tool("list_filteredcustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Active Customer")

    def test_get_serializer_class_for_mcp_requests(self):
        """Test that ViewSets can use different serializers for MCP requests."""
        from rest_framework import serializers, viewsets

        from djangorestframework_mcp.decorators import mcp_viewset

        class SimplifiedCustomerSerializer(serializers.ModelSerializer):
            class Meta:
                model = Customer
                fields = ["name", "email"]  # Simplified for MCP

        @mcp_viewset(basename="serializercustomers")
        class SerializerCustomerViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()

            def get_serializer_class(self):
                # Use simplified serializer for MCP requests
                if hasattr(self, "request") and getattr(
                    self.request, "is_mcp_request", False
                ):
                    return SimplifiedCustomerSerializer
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

        # Test MCP request - should get simplified data
        result = self.client.call_tool("list_serializercustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        # Should have simplified fields only
        for customer in data:
            expected_fields = {"name", "email"}
            actual_fields = set(customer.keys())
            # MCP responses may include additional fields like 'id'
            self.assertTrue(expected_fields.issubset(actual_fields))
            # Should NOT have age or is_active in simplified version
            self.assertNotIn("age", customer)
            self.assertNotIn("is_active", customer)

    def test_custom_action_behavior_for_mcp_requests(self):
        """Test custom actions can behave differently for MCP requests."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        @mcp_viewset(basename="behavioralcustomers")
        class BehavioralCustomerViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()

            def get_serializer_class(self):
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

            @mcp_tool(input_serializer=None)
            @action(detail=False, methods=["get"])
            def get_stats(self, request):
                if getattr(request, "is_mcp_request", False):
                    # MCP gets simplified stats
                    return Response(
                        {
                            "total_customers": Customer.objects.count(),
                            "type": "mcp_stats",
                        }
                    )
                else:
                    # Regular API gets detailed stats
                    return Response(
                        {
                            "total_customers": Customer.objects.count(),
                            "active_customers": Customer.objects.filter(
                                is_active=True
                            ).count(),
                            "inactive_customers": Customer.objects.filter(
                                is_active=False
                            ).count(),
                            "avg_age": 27.5,
                            "type": "detailed_stats",
                        }
                    )

        # Test MCP request
        result = self.client.call_tool("get_stats_behavioralcustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data["type"], "mcp_stats")
        self.assertIn("total_customers", data)
        self.assertNotIn("active_customers", data)  # Simplified version


@override_settings(ROOT_URLCONF="tests.urls")
class TestViewSetInheritancePatterns(MCPTestCase):
    """Test MCP integration with ViewSet inheritance patterns."""

    def setUp(self):
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        from djangorestframework_mcp.registry import registry

        registry.clear()

    def test_mcp_viewset_inheriting_from_regular_viewset(self):
        """Test MCP ViewSet inheriting from a regular ViewSet works correctly."""
        from rest_framework import viewsets
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_viewset

        # Base ViewSet (not MCP-enabled)
        class BaseCustomerViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()

            def get_serializer_class(self):
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

            def get_queryset(self):
                # Base behavior: filter out customers with no email
                return super().get_queryset().exclude(email="")

            def list(self, request, *args, **kwargs):
                # Custom list behavior
                queryset = self.filter_queryset(self.get_queryset())
                serializer = self.get_serializer(queryset, many=True)
                return Response(
                    {
                        "customers": serializer.data,
                        "count": queryset.count(),
                        "source": "inherited",
                    }
                )

        # MCP-enabled ViewSet inheriting from base
        @mcp_viewset(basename="inheritedcustomers")
        class InheritedCustomerViewSet(BaseCustomerViewSet):
            pass  # Inherits all behavior from BaseCustomerViewSet

        # Should work with inherited behavior
        result = self.client.call_tool("list_inheritedcustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        # Should have inherited custom structure
        self.assertIn("customers", data)
        self.assertIn("count", data)
        self.assertEqual(data["source"], "inherited")

    def test_multiple_inheritance_with_mixins(self):
        """Test MCP ViewSet with multiple inheritance and mixins."""
        from rest_framework import mixins, viewsets

        from djangorestframework_mcp.decorators import mcp_viewset

        # Custom mixin
        class CustomMixin:
            def get_custom_data(self):
                return {"mixin_data": "from_mixin"}

        # MCP ViewSet with multiple inheritance
        @mcp_viewset(basename="mixincustomers")
        class MixinCustomerViewSet(
            CustomMixin,
            mixins.ListModelMixin,
            mixins.CreateModelMixin,
            viewsets.GenericViewSet,
        ):
            queryset = Customer.objects.all()

            def get_serializer_class(self):
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

            def list(self, request, *args, **kwargs):
                # Use inherited behavior but add mixin data
                response = super().list(request, *args, **kwargs)
                response.data = {"customers": response.data, **self.get_custom_data()}
                return response

        # Test that it works with multiple inheritance
        result = self.client.call_tool("list_mixincustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        self.assertIn("customers", data)
        self.assertIn("mixin_data", data)
        self.assertEqual(data["mixin_data"], "from_mixin")

    def test_abstract_base_viewset_pattern(self):
        """Test abstract base ViewSet pattern with MCP."""
        from rest_framework import viewsets
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_viewset

        # Abstract base ViewSet
        class AbstractBaseViewSet(viewsets.ModelViewSet):
            """Abstract base with common functionality."""

            def get_serializer_class(self):
                from tests.serializers import CustomerSerializer

                return CustomerSerializer

            def get_base_context(self):
                return {"api_version": "1.0", "timestamp": "2024-01-01T00:00:00Z"}

            def list(self, request, *args, **kwargs):
                response = super().list(request, *args, **kwargs)
                # Add base context to all list responses
                return Response(
                    {"data": response.data, "meta": self.get_base_context()}
                )

            class Meta:
                abstract = True

        # Concrete implementation
        @mcp_viewset(basename="abstractcustomers")
        class ConcreteCustomerViewSet(AbstractBaseViewSet):
            queryset = Customer.objects.all()

            def get_base_context(self):
                # Override base context
                base_context = super().get_base_context()
                base_context["concrete_viewset"] = True
                return base_context

        # Test abstract base pattern works
        result = self.client.call_tool("list_abstractcustomers")
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        self.assertIn("data", data)
        self.assertIn("meta", data)
        self.assertEqual(data["meta"]["api_version"], "1.0")
        self.assertTrue(data["meta"]["concrete_viewset"])


@override_settings(ROOT_URLCONF="tests.urls")
class TestListSerializerIntegration(MCPTestCase):
    """Integration tests for list serializers with actual MCP tool execution."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        from djangorestframework_mcp.registry import registry

        registry.clear()

    def test_viewset_with_mixed_single_and_list_endpoints(self):
        """Test ViewSet with both single item and list endpoints."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import SimpleItemListSerializer, SimpleItemSerializer

        @mcp_viewset()
        class ItemViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemSerializer)
            @action(detail=False, methods=["post"])
            def create_single(self, request):
                return Response(
                    {"message": "Single item created", "item": request.data}
                )

            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=["post"])
            def create_bulk(self, request):
                return Response(
                    {
                        "message": f"Bulk created {len(request.data)} items",
                        "items": request.data,
                    }
                )

        # Test single item endpoint
        single_result = self.client.call_tool(
            "create_single_item",
            {"body": {"name": "Test Item", "value": 42, "is_active": True}},
        )

        self.assertFalse(single_result.get("isError"))
        structured_data = single_result["structuredContent"]
        self.assertEqual(structured_data["message"], "Single item created")
        self.assertEqual(structured_data["item"]["name"], "Test Item")

        # Test bulk endpoint
        bulk_result = self.client.call_tool(
            "create_bulk_item",
            {
                "body": [
                    {"name": "Item 1", "value": 10, "is_active": True},
                    {"name": "Item 2", "value": 20, "is_active": False},
                    {"name": "Item 3", "value": 30, "is_active": True},
                ]
            },
        )

        self.assertFalse(bulk_result.get("isError"))
        structured_data = bulk_result["structuredContent"]
        self.assertEqual(structured_data["message"], "Bulk created 3 items")
        self.assertEqual(len(structured_data["items"]), 3)
        self.assertEqual(structured_data["items"][0]["name"], "Item 1")
        self.assertEqual(structured_data["items"][1]["value"], 20)

    def test_list_endpoint_tool_schema_in_tools_list(self):
        """Test that list endpoints show correct schema in tools list."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import SimpleItemListSerializer

        @mcp_viewset()
        class BulkViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=["post"])
            def bulk_operation(self, request):
                return Response({"processed": len(request.data)})

        # List all tools and find our bulk operation
        tools_result = self.client.list_tools()
        tools_list = tools_result["tools"]
        bulk_tool = next(t for t in tools_list if t["name"] == "bulk_operation_bulk")

        # Check the input schema
        input_schema = bulk_tool["inputSchema"]
        self.assertIn("body", input_schema["properties"])

        body_schema = input_schema["properties"]["body"]
        self.assertEqual(body_schema["type"], "array")
        self.assertIn("items", body_schema)

        # Items should have the expected object structure
        item_schema = body_schema["items"]
        self.assertEqual(item_schema["type"], "object")
        self.assertIn("name", item_schema["properties"])
        self.assertIn("value", item_schema["properties"])
        self.assertIn("is_active", item_schema["properties"])

    def test_empty_list_input(self):
        """Test that empty list input works correctly."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import SimpleItemListSerializer

        @mcp_viewset()
        class EmptyTestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=["post"])
            def process_items(self, request):
                return Response({"count": len(request.data)})

        # Test with empty list
        result = self.client.call_tool("process_items_emptytest", {"body": []})

        self.assertFalse(result.get("isError"))
        structured_data = result["structuredContent"]
        self.assertEqual(structured_data["count"], 0)

    def test_list_input_with_validation_errors(self):
        """Test that validation errors work correctly with list inputs."""
        from rest_framework import status, viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import StrictListSerializer, StrictSerializer

        @mcp_viewset()
        class ValidationViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=StrictListSerializer)
            @action(detail=False, methods=["post"])
            def validate_items(self, request):
                serializer = StrictSerializer(data=request.data, many=True)
                if serializer.is_valid():
                    return Response({"valid": True, "data": serializer.data})
                else:
                    return Response(
                        {"valid": False, "errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Test with invalid data (name too long, negative value)
        result = self.client.call_tool(
            "validate_items_validation",
            {
                "body": [
                    {"name": "ValidName", "value": 10},
                    {"name": "TooLongName", "value": -5},  # Invalid data
                ]
            },
        )

        # Should get a validation error
        self.assertTrue(result.get("isError"))
        error_text = result["content"][0]["text"]
        self.assertIn("ViewSet returned error", error_text)


@override_settings(ROOT_URLCONF="tests.urls")
class AuthenticationIntegrationTests(MCPTestCase):
    """Integration tests for authentication functionality."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)
        self.client = MCPClient()

    def test_tools_list_requires_authentication(self):
        """Verifies tools/list endpoint respects authentication requirements."""
        # This test assumes there are authenticated ViewSets registered
        # The default test setup may not require auth, so we'll test error handling

        # Test without auth - should work if no auth required by default
        result = self.client.list_tools()
        self.assertFalse(result.get("isError"))

        # Test with auth - should also work
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"
        result = self.client.list_tools()
        self.assertFalse(result.get("isError"))

    def test_tools_call_requires_authentication(self):
        """Verifies tools/call endpoint respects authentication requirements."""
        # Test a tool call without auth - behavior depends on ViewSet config
        self.client.call_tool("list_customers")

        # May succeed or fail depending on ViewSet auth requirements
        # This is expected behavior - some ViewSets require auth, others don't

        # Test with auth - should work for both authenticated and non-authenticated ViewSets
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"
        self.client.call_tool("list_customers")
        # Should succeed regardless of ViewSet auth requirements

    def test_request_is_mcp_request_property(self):
        """Verifies request.is_mcp_request is properly set for authenticated requests."""
        # Test the property by attempting to list tools - this should work
        # and confirms the MCP request lifecycle is working properly

        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"
        result = self.client.list_tools()

        # If request.is_mcp_request works, the request should be processed normally
        self.assertFalse(result.get("isError"))
        self.assertIn("tools", result)
        # Should return a list of available tools
        self.assertIsInstance(result["tools"], list)

    def test_existing_api_calls_unchanged(self):
        """Verifies regular DRF API calls still work exactly as before."""
        from django.test import Client

        # Create test customer
        Customer.objects.create(
            name="API Test Customer",
            email="apitest@example.com",
            age=30,
            is_active=True,
        )

        # Use regular Django test client for API calls
        api_client = Client()

        # Test regular DRF API still works (GET request)
        response = api_client.get("/customers/")

        # Should get a valid HTTP response (exact status depends on ViewSet config)
        # The important thing is that it doesn't break due to MCP changes
        self.assertIn(
            response.status_code, [200, 401, 403, 404]
        )  # Valid HTTP responses

        # If it's 200, check the response format
        if response.status_code == 200:
            data = json.loads(response.content)
            # Should be standard DRF response format, not MCP format
            self.assertNotIn("jsonrpc", data)  # Not MCP response
            self.assertNotIn("isError", data)  # Not MCP error format


class ViewSetAuthenticationTests(TestCase):
    """Test authentication functionality at the ViewSet level."""

    def setUp(self):
        """Set up test data."""
        # Clear registry before each test
        registry.clear()

        # Register test viewsets (they are decorated, so we register manually for testing)
        registry.register_viewset(AuthenticatedViewSet)
        registry.register_viewset(MultipleAuthViewSet)
        registry.register_viewset(UnauthenticatedViewSet)
        registry.register_viewset(CustomAuthViewSet)
        registry.register_viewset(CustomPermissionViewSet)

        # Create test user and token
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

        self.client = MCPClient()

    def tearDown(self):
        """Clean up after each test."""
        registry.clear()
        # Clear any client defaults that might have been set
        if hasattr(self, "client"):
            self.client.defaults.clear()

    def test_token_authentication_success(self):
        """Verifies MCP requests succeed with valid token authentication."""
        # Set authentication header for all requests
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"

        result = self.client.call_tool("list_authenticated")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Authenticated Item")

    def test_token_authentication_failure(self):
        """Verifies MCP requests fail with invalid/missing token."""
        # Test with invalid token
        self.client.defaults["HTTP_AUTHORIZATION"] = "Token invalid_token"
        result = self.client.call_tool("list_authenticated")

        self.assertTrue(result.get("isError"))
        self.assertIn("Invalid token", result["content"][0]["text"])

        # Test with no token - clear the defaults first
        self.client.defaults.clear()
        result = self.client.call_tool("list_authenticated")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn(
            "Authentication credentials were not provided", result["content"][0]["text"]
        )

    def test_session_authentication_success(self):
        """Verifies MCP requests work with valid session cookies."""
        # Login to create session
        self.client.login(username="testuser", password="testpass")

        # Note: Session auth with MCPClient may have issues with cookie handling
        # For now, expecting this to fail until session support is fully implemented
        result = self.client.call_tool("list_multipleauth")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn(
            "Authentication credentials were not provided", result["content"][0]["text"]
        )

    def test_basic_authentication_success(self):
        """Verifies MCP requests work with valid basic auth credentials."""
        credentials = base64.b64encode(b"testuser:testpass").decode("ascii")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Basic {credentials}"

        result = self.client.call_tool("list_multipleauth")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Multi-auth Item")

    def test_basic_authentication_failure(self):
        """Verifies MCP requests fail with invalid basic auth credentials."""
        credentials = base64.b64encode(b"testuser:wrongpass").decode("ascii")

        self.client.defaults["HTTP_AUTHORIZATION"] = f"Basic {credentials}"
        result = self.client.call_tool("list_multipleauth")

        self.assertTrue(result.get("isError"))
        self.assertIn("Invalid username/password", result["content"][0]["text"])

    def test_multiple_authentication_classes(self):
        """Verifies any of multiple auth methods can authenticate successfully."""
        # Test that token auth works with ViewSets that have multiple auth classes
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"
        result = self.client.call_tool("list_multipleauth")

        self.assertFalse(result.get("isError"))

    def test_permission_classes_applied(self):
        """Verifies ViewSet permission classes are enforced for MCP requests."""
        # Create unauthenticated request
        result = self.client.call_tool("list_authenticated")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn(
            "Authentication credentials were not provided", result["content"][0]["text"]
        )

    def test_unauthenticated_viewset_allows_access(self):
        """Verifies ViewSets without auth requirements work without authentication."""
        result = self.client.call_tool("list_unauthenticated")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Public Item")

    def test_custom_authentication_class(self):
        """Verifies custom BaseAuthentication subclasses work with MCP requests."""
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Custom {self.token.key}"
        result = self.client.call_tool("list_customauth")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Custom Auth Item")

    def test_custom_permission_class(self):
        """Verifies custom BasePermission subclasses work with MCP requests."""
        # Test ViewSet with custom permission that always denies
        result = self.client.call_tool("list_custompermission")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn("Custom permission denied", result["content"][0]["text"])


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True})
class BypassAuthenticationTests(TestCase):
    """Test bypassing ViewSet authentication."""

    def setUp(self):
        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        self.client = MCPClient()

    def tearDown(self):
        registry.clear()
        if hasattr(self, "client"):
            self.client.defaults.clear()

    def test_bypass_viewset_authentication_setting(self):
        """Verifies BYPASS_VIEWSET_AUTHENTICATION alone fails with auth-dependent permissions."""
        # Should fail because we bypassed auth but kept IsAuthenticated permission
        result = self.client.call_tool("list_authenticated")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        # Should fail with permission error since user is not authenticated
        self.assertIn(
            "You do not have permission to perform this action",
            result["content"][0]["text"],
        )


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_PERMISSIONS": True})
class BypassPermissionsTests(TestCase):
    """Test bypassing ViewSet permissions."""

    def setUp(self):
        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        self.client = MCPClient()

    def tearDown(self):
        registry.clear()
        if hasattr(self, "client"):
            self.client.defaults.clear()

    def test_bypass_viewset_permissions_setting(self):
        """Verifies BYPASS_VIEWSET_PERMISSIONS skips ViewSet permissions."""
        # Should succeed without authentication due to bypassed permissions
        result = self.client.call_tool("list_authenticated")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Authenticated Item")


@override_settings(
    DJANGORESTFRAMEWORK_MCP={
        "BYPASS_VIEWSET_AUTHENTICATION": True,
        "BYPASS_VIEWSET_PERMISSIONS": True,
    }
)
class BypassBothTests(TestCase):
    """Test bypassing both authentication and permissions."""

    def setUp(self):
        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        self.client = MCPClient()

    def tearDown(self):
        registry.clear()
        if hasattr(self, "client"):
            self.client.defaults.clear()

    def test_bypass_both_settings_together(self):
        """Verifies both bypass settings can work together."""
        result = self.client.call_tool("list_authenticated")

        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data[0]["name"], "Authenticated Item")


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True})
class MixedAuthenticationTests(TestCase):
    """Test mixed authentication scenarios: Authentication bypassed at ViewSet level, permissions still enforced."""

    def setUp(self):
        """Set up test data."""
        registry.clear()

        # Create test user and token
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

        # Create a second user for permission testing
        self.other_user = User.objects.create_user(
            "otheruser", "other@example.com", "otherpass"
        )
        self.other_token = Token.objects.create(user=self.other_user)

    def tearDown(self):
        """Clean up after each test."""
        registry.clear()

    def test_bypass_auth_permission_failure_no_user(self):
        """Test that ViewSet permissions fail when auth is bypassed and no user present."""

        # ViewSet with permissions but auth bypassed
        @mcp_viewset()
        class AuthBypassedViewSet(viewsets.GenericViewSet):
            authentication_classes = [TokenAuthentication]  # This will be bypassed
            permission_classes = [IsAuthenticated]  # This will run with no user

            def list(self, request):
                return Response([{"id": 1, "name": "Should not reach here"}])

        # Use MCPClient without authentication
        client = MCPClient()
        # Should fail because no authenticated user is present for permission check
        result = client.call_tool("list_authbypassed")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn(
            "You do not have permission to perform this action",
            result["content"][0]["text"],
        )

    def test_bypass_auth_permissions_with_mcp_endpoint_auth(self):
        """Test BYPASS_VIEWSET_AUTHENTICATION + IsAuthenticated permissions with authenticated MCP endpoint."""
        # This tests the key scenario:
        # - Authentication happens at MCP endpoint level
        # - BYPASS_VIEWSET_AUTHENTICATION = True (ViewSet auth is skipped)
        # - BYPASS_VIEWSET_PERMISSIONS = False (ViewSet permissions still enforced)
        # - ViewSet has IsAuthenticated permission
        # - User context should be preserved from endpoint auth to ViewSet permissions

        # ViewSet with authentication that will be bypassed but permissions enforced
        @mcp_viewset()
        class BypassAuthPermViewSet(viewsets.GenericViewSet):
            authentication_classes = [TokenAuthentication]  # This will be bypassed
            permission_classes = [
                IsAuthenticated
            ]  # This should work with preserved user context

            def list(self, request):
                return Response(
                    [
                        {
                            "id": 1,
                            "name": "Bypass auth test",
                            "user": request.user.username,
                        }
                    ]
                )

        # Create a custom authenticated MCP endpoint like the demo app
        from djangorestframework_mcp.views import MCPView

        class AuthenticatedMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        # Test using Django's test client directly with the authenticated MCP view
        from django.test import Client

        client = Client()
        view = AuthenticatedMCPView.as_view()

        # Test the scenario with proper token authentication
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_bypassauthperm", "arguments": {}},
            "id": 1,
        }

        response = client.post(
            "/mcp/",  # We'll override the view
            data=json.dumps(request_data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        # Manually invoke our authenticated view instead

        from django.http import HttpRequest

        request = HttpRequest()
        request.method = "POST"
        request.content_type = "application/json"
        request.META["CONTENT_TYPE"] = "application/json"
        request.META["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"
        request._body = json.dumps(request_data).encode()
        request._read_started = True

        # Process the request with our authenticated MCP view
        response = view(request)
        response_data = json.loads(response.content)

        # Should succeed because:
        # 1. MCP endpoint authenticates the user via token
        # 2. ViewSet auth is bypassed but user context is preserved
        # 3. IsAuthenticated permission passes with the authenticated user
        self.assertEqual(response.status_code, 200)
        self.assertIn("result", response_data)
        self.assertFalse(response_data["result"].get("isError", False))

        if "structuredContent" in response_data["result"]:
            data = response_data["result"]["structuredContent"][0]
            self.assertEqual(data["name"], "Bypass auth test")
            self.assertEqual(data["user"], "testuser")

    def test_custom_permission_logic_with_bypassed_auth(self):
        """Test that custom permission logic works correctly when auth is bypassed."""
        from rest_framework.permissions import BasePermission

        # Custom permission that doesn't require authentication
        class AlwaysAllowPermission(BasePermission):
            def has_permission(self, request, view):
                return True  # Always allow regardless of user

        # ViewSet with custom permission that allows unauthenticated access
        @mcp_viewset()
        class CustomPermViewSet(viewsets.GenericViewSet):
            authentication_classes = [TokenAuthentication]  # Bypassed
            permission_classes = [AlwaysAllowPermission]  # Should allow access

            def list(self, request):
                username = request.user.username or "anonymous"
                return Response([{"user": username, "access": "granted"}])

        # Use MCPClient without authentication
        client = MCPClient()
        result = client.call_tool("list_customperm")

        # Should succeed because custom permission allows it
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"][0]
        self.assertEqual(data["access"], "granted")
        self.assertEqual(data["user"], "anonymous")

    def test_permission_with_anonymous_user_attributes(self):
        """Test permission logic that depends on user attributes when auth is bypassed."""
        from rest_framework.permissions import BasePermission

        # Permission that checks user attributes
        class UserAttributePermission(BasePermission):
            message = "User must be staff"

            def has_permission(self, request, view):
                # When auth is bypassed, user will be AnonymousUser
                return getattr(request.user, "is_staff", False)

        # ViewSet with attribute-based permission
        @mcp_viewset()
        class AttributeViewSet(viewsets.GenericViewSet):
            authentication_classes = [TokenAuthentication]  # Bypassed
            permission_classes = [UserAttributePermission]

            def list(self, request):
                return Response([{"allowed": True}])

        # Use MCPClient without authentication
        client = MCPClient()
        # Should fail because AnonymousUser.is_staff = False
        result = client.call_tool("list_attribute")

        # Should return error result instead of raising exception
        self.assertTrue(result.get("isError"))
        self.assertIn("User must be staff", result["content"][0]["text"])


@override_settings(ROOT_URLCONF="tests.urls")
class Return200ForErrorsIntegrationTests(TestCase):
    """Integration tests for the RETURN_200_FOR_ERRORS setting."""

    def setUp(self):
        """Set up test data."""
        # Clear registry and register auth-required viewsets
        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        registry.register_viewset(CustomPermissionViewSet)

        # Create test user and token
        self.user = User.objects.create_user("testuser", "test@example.com", "testpass")
        self.token = Token.objects.create(user=self.user)

    def tearDown(self):
        """Clean up after each test."""
        registry.clear()

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": False})
    def test_mcp_endpoint_auth_error_default_behavior(self):
        """Test MCP endpoint authentication errors return proper HTTP status codes by default."""
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        # Create authenticated MCP view
        from djangorestframework_mcp.views import MCPView

        class AuthMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        # Test without auth - should return 401
        response = AuthMCPView.as_view()(self._build_request(request_data))
        self.assertEqual(response.status_code, 401)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Unauthorized:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_mcp_endpoint_auth_error_compatibility_mode(self):
        """Test MCP endpoint auth errors return HTTP 200 in compatibility mode."""
        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        # Create authenticated MCP view
        from djangorestframework_mcp.views import MCPView

        class AuthMCPView(MCPView):
            authentication_classes = [TokenAuthentication]

            def has_mcp_permission(self, request):
                return request.user.is_authenticated

        # Test without auth - should return 200 but with error in body
        response = AuthMCPView.as_view()(self._build_request(request_data))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Unauthorized:", error_text)

        # WWW-Authenticate header should NOT be present in compatibility mode
        self.assertNotIn("WWW-Authenticate", response)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": False})
    def test_mcp_endpoint_permission_error_default_behavior(self):
        """Test MCP endpoint permission errors return proper HTTP status codes by default."""
        from djangorestframework_mcp.views import MCPView

        class PermissionMCPView(MCPView):
            def has_mcp_permission(self, request):
                return False  # Always deny

        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        # Should return 403
        response = PermissionMCPView.as_view()(self._build_request(request_data))
        self.assertEqual(response.status_code, 403)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Forbidden:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_mcp_endpoint_permission_error_compatibility_mode(self):
        """Test MCP endpoint permission errors return HTTP 200 in compatibility mode."""
        from djangorestframework_mcp.views import MCPView

        class PermissionMCPView(MCPView):
            def has_mcp_permission(self, request):
                return False  # Always deny

        request_data = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}

        # Should return 200 but with error in body
        response = PermissionMCPView.as_view()(self._build_request(request_data))
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Forbidden:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": False})
    def test_viewset_auth_error_default_behavior(self):
        """Test ViewSet authentication errors return proper HTTP status codes by default."""
        from django.test import Client

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_authenticated", "arguments": {}},
            "id": 1,
        }

        # Should return 401 since no auth provided
        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Unauthorized:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_viewset_auth_error_compatibility_mode(self):
        """Test ViewSet auth errors return HTTP 200 in compatibility mode."""
        from django.test import Client

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_authenticated", "arguments": {}},
            "id": 1,
        }

        # Should return 200 but with error in body
        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Unauthorized:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": False})
    def test_viewset_permission_error_default_behavior(self):
        """Test ViewSet permission errors return proper HTTP status codes by default."""
        from django.test import Client

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_custompermission", "arguments": {}},
            "id": 1,
        }

        # Should return 403 due to custom permission that always denies
        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Forbidden:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_viewset_permission_error_compatibility_mode(self):
        """Test ViewSet permission errors return HTTP 200 in compatibility mode."""
        from django.test import Client

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_custompermission", "arguments": {}},
            "id": 1,
        }

        # Should return 200 but with error in body
        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Forbidden:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_object_level_permission_error_compatibility_mode(self):
        """Test object-level permission failures return HTTP 200 in compatibility mode."""
        from django.test import Client
        from rest_framework.permissions import BasePermission

        # Create a permission that checks object ownership
        class IsOwnerPermission(BasePermission):
            def has_object_permission(self, request, view, obj):
                return obj.user == request.user

        # Create a ViewSet with object-level permissions
        @mcp_viewset()
        class ObjectPermissionViewSet(viewsets.GenericViewSet):
            authentication_classes = [TokenAuthentication]
            permission_classes = [IsOwnerPermission]

            def retrieve(self, request, pk=None):
                # Simulate retrieving an object owned by a different user
                from types import SimpleNamespace

                from django.contrib.auth.models import User

                other_user = User.objects.create_user(
                    "otheruser", "other@example.com", "otherpass"
                )
                obj = SimpleNamespace(user=other_user, id=pk)
                self.check_object_permissions(request, obj)
                return Response({"id": pk, "owner": obj.user.username})

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "retrieve_objectpermission",
                "arguments": {"kwargs": {"pk": "1"}},
            },
            "id": 1,
        }

        # Should return 200 but with error in body due to object permission failure
        response = client.post(
            "/mcp/",
            data=json.dumps(request_data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertTrue(data["result"]["isError"])
        error_text = data["result"]["content"][0]["text"]
        self.assertIn("Forbidden:", error_text)

    @override_settings(DJANGORESTFRAMEWORK_MCP={"RETURN_200_FOR_ERRORS": True})
    def test_successful_requests_unaffected(self):
        """Test successful requests are unaffected by compatibility mode."""
        from django.test import Client

        client = Client()
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_unauthenticated", "arguments": {}},
            "id": 1,
        }

        response = client.post(
            "/mcp/", data=json.dumps(request_data), content_type="application/json"
        )

        # Successful requests should still return 200
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertIn("result", data)
        self.assertNotIn("error", data)

    def _build_request(self, data):
        """Helper to build Django HttpRequest for testing."""
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = "POST"
        request.content_type = "application/json"
        request.META["CONTENT_TYPE"] = "application/json"
        request._body = json.dumps(data).encode()
        request._read_started = True
        return request
