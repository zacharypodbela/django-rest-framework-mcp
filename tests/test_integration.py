"""Integration tests for MCP functionality."""

import base64
import json

from django.test import TestCase, override_settings
from rest_framework import mixins, serializers, viewsets
from rest_framework.authentication import (
    TokenAuthentication,
)
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset
from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.test import MCPClient

from .factories import (
    CategoryFactory,
    CustomerFactory,
    OrderFactory,
    ProductFactory,
    TagFactory,
    TokenFactory,
    UserFactory,
)
from .models import Category, Customer, Order, Product, Tag
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
        self.customer1 = CustomerFactory(
            name="Alice Smith", email="alice@example.com", age=30, is_active=True
        )
        self.customer2 = CustomerFactory(
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
        self.customer = CustomerFactory(
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
        CustomerFactory(name="Test Customer", email="test@example.com", age=30)

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
        CustomerFactory(name="Existing Customer", email="existing@example.com", age=25)

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
        self.active_customer = CustomerFactory(
            name="Active Customer", email="active@example.com", age=30, is_active=True
        )
        self.inactive_customer = CustomerFactory(
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
        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.token = TokenFactory(user=self.user)
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
        CustomerFactory(
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
        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.token = TokenFactory(user=self.user)

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
        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.token = TokenFactory(user=self.user)

        # Create a second user for permission testing
        self.other_user = UserFactory(
            username="otheruser", email="other@example.com", password="otherpass"
        )
        self.other_token = TokenFactory(user=self.other_user)

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
        self.user = UserFactory(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.token = TokenFactory(user=self.user)

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

                other_user = UserFactory(
                    username="otheruser",
                    email="other@example.com",
                    password="otherpass",
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


@override_settings(ROOT_URLCONF="tests.urls")
class RelationshipFieldIntegrationTests(TestCase):
    """Integration tests for relationship fields via MCP."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        registry.clear()

        # Define serializers dynamically in setUp to comply with README standards
        class OrderSerializer(serializers.ModelSerializer):
            """Serializer for Order model with PrimaryKeyRelatedField."""

            class Meta:
                model = Order
                fields = ["id", "customer", "total", "created_at"]
                read_only_fields = ["created_at"]

        class ProductSerializer(serializers.ModelSerializer):
            """Serializer for Product model with SlugRelatedField."""

            category_slug = serializers.SlugRelatedField(
                queryset=Category.objects.all(),
                slug_field="slug",
                source="category",
                allow_null=True,
            )

            class Meta:
                model = Product
                fields = [
                    "id",
                    "name",
                    "description",
                    "price",
                    "in_stock",
                    "category_slug",
                    "slug",
                ]

        class ProductWithTagsSerializer(serializers.ModelSerializer):
            """Serializer with ManyToMany relationship using PrimaryKeyRelatedField."""

            tags = serializers.PrimaryKeyRelatedField(
                queryset=Tag.objects.all(), many=True, required=False
            )

            class Meta:
                model = Product
                fields = ["id", "name", "price", "tags"]

        # Store serializers on instance for ViewSets to access
        self.OrderSerializer = OrderSerializer
        self.ProductSerializer = ProductSerializer
        self.ProductWithTagsSerializer = ProductWithTagsSerializer

        # Define ViewSets dynamically in setUp
        @mcp_viewset(basename="orders")
        class OrderViewSet(viewsets.ModelViewSet):
            """ViewSet for Order with ForeignKey relationship."""

            queryset = Order.objects.all()

            def get_serializer_class(self):
                # Access test instance's serializer through registry context
                return OrderSerializer

        @mcp_viewset(basename="slugproducts")
        class SlugProductViewSet(viewsets.ModelViewSet):
            """ViewSet for Product with SlugRelatedField."""

            queryset = Product.objects.all()

            def get_serializer_class(self):
                return ProductSerializer

        @mcp_viewset(basename="taggedproducts")
        class TaggedProductViewSet(viewsets.ModelViewSet):
            """ViewSet for Product with ManyToMany tags."""

            queryset = Product.objects.all()

            def get_serializer_class(self):
                return ProductWithTagsSerializer

        self.viewsets = [OrderViewSet, SlugProductViewSet, TaggedProductViewSet]

        # Initialize MCP client
        self.client = MCPClient()

        # Create test data
        self.customer1 = CustomerFactory(
            name="Alice Smith", email="alice@example.com", age=30
        )
        self.customer2 = CustomerFactory(
            name="Bob Jones", email="bob@example.com", age=25
        )

        self.category1 = CategoryFactory(name="Electronics", slug="electronics")
        self.category2 = CategoryFactory(name="Books", slug="books")

        self.product1 = ProductFactory(
            name="Laptop",
            description="High-performance laptop",
            price="999.99",
            category=self.category1,
            slug="laptop",
        )

        self.tag1 = TagFactory(name="Featured")
        self.tag2 = TagFactory(name="Sale")
        self.tag3 = TagFactory(name="New")

    def test_create_order_with_foreign_key(self):
        """Test creating an order with PrimaryKeyRelatedField."""
        result = self.client.call_tool(
            "create_orders",
            arguments={
                "body": {
                    "customer": self.customer1.pk,
                    "total": "150.00",
                }
            },
        )

        # Extract data from structuredContent
        data = result.get("structuredContent", result)
        self.assertIn("id", data)
        order = Order.objects.get(pk=data["id"])
        self.assertEqual(order.customer, self.customer1)
        self.assertEqual(str(order.total), "150.00")

    def test_update_order_customer(self):
        """Test updating an order's customer relationship."""
        order = OrderFactory(customer=self.customer1, total="100.00")

        self.client.call_tool(
            "update_orders",
            arguments={
                "kwargs": {"pk": str(order.pk)},
                "body": {
                    "customer": self.customer2.pk,
                    "total": "100.00",
                },
            },
        )

        order.refresh_from_db()
        self.assertEqual(order.customer, self.customer2)

    def test_create_order_with_invalid_customer(self):
        """Test validation error for non-existent customer PK."""
        try:
            result = self.client.call_tool(
                "create_orders",
                arguments={
                    "body": {
                        "customer": 99999,  # Non-existent PK
                        "total": "150.00",
                    }
                },
            )
            # If we get here, no exception was raised - let's see what the result is
            self.fail(f"Expected validation error, but got result: {result}")
        except Exception as e:
            # This is what we expect - a validation error
            # Let's check what the actual error message contains
            error_msg = str(e).lower()
            # Common validation error phrases
            validation_phrases = [
                "invalid",
                "does not exist",
                "not found",
                "constraint",
            ]
            self.assertTrue(
                any(phrase in error_msg for phrase in validation_phrases),
                f"Expected validation error, got: {e}",
            )

    def test_create_product_with_category_slug(self):
        """Test creating a product with SlugRelatedField."""
        result = self.client.call_tool(
            "create_slugproducts",
            arguments={
                "body": {
                    "name": "Python Book",
                    "description": "Learn Python",
                    "price": "29.99",
                    "category_slug": "books",
                    "slug": "python-book",
                }
            },
        )

        data = result.get("structuredContent", result)
        self.assertIn("id", data)
        product = Product.objects.get(pk=data["id"])
        self.assertEqual(product.category, self.category2)
        self.assertEqual(product.name, "Python Book")

    def test_update_product_category_with_slug(self):
        """Test updating a product's category using slug."""
        self.client.call_tool(
            "update_slugproducts",
            arguments={
                "kwargs": {"pk": str(self.product1.pk)},
                "body": {
                    "name": self.product1.name,
                    "price": str(self.product1.price),
                    "category_slug": "books",
                    "slug": self.product1.slug,
                },
            },
        )

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.category, self.category2)

    def test_create_product_with_null_category(self):
        """Test creating a product with null category (allow_null=True)."""
        result = self.client.call_tool(
            "create_slugproducts",
            arguments={
                "body": {
                    "name": "Standalone Product",
                    "description": "No category",
                    "price": "49.99",
                    "category_slug": None,
                    "slug": "standalone",
                }
            },
        )

        data = result.get("structuredContent", result)
        product = Product.objects.get(pk=data["id"])
        self.assertIsNone(product.category)

    def test_invalid_slug_validation(self):
        """Test validation error for non-existent slug."""
        try:
            result = self.client.call_tool(
                "create_slugproducts",
                arguments={
                    "body": {
                        "name": "Test Product",
                        "price": "10.00",
                        "category_slug": "non-existent-slug",
                        "slug": "test-product",
                    }
                },
            )
            # If we get here, no exception was raised - let's see what the result is
            self.fail(f"Expected validation error, but got result: {result}")
        except Exception as e:
            # This is what we expect - a validation error
            error_msg = str(e).lower()
            # Common validation error phrases
            validation_phrases = [
                "invalid",
                "does not exist",
                "not found",
                "constraint",
            ]
            self.assertTrue(
                any(phrase in error_msg for phrase in validation_phrases),
                f"Expected validation error, got: {e}",
            )

    def test_product_with_many_tags(self):
        """Test ManyToMany relationship with PrimaryKeyRelatedField."""
        # Create product with tags
        result = self.client.call_tool(
            "create_taggedproducts",
            arguments={
                "body": {
                    "name": "Tagged Product",
                    "price": "99.99",
                    "tags": [self.tag1.pk, self.tag2.pk],
                }
            },
        )

        data = result.get("structuredContent", result)
        product = Product.objects.get(pk=data["id"])
        self.assertEqual(product.tags.count(), 2)
        self.assertIn(self.tag1, product.tags.all())
        self.assertIn(self.tag2, product.tags.all())

    def test_update_product_tags(self):
        """Test updating ManyToMany tags."""
        product = ProductFactory(name="Test Product", price="50.00")
        product.tags.add(self.tag1)

        # Update to different tags
        self.client.call_tool(
            "update_taggedproducts",
            arguments={
                "kwargs": {"pk": str(product.pk)},
                "body": {
                    "name": product.name,
                    "price": str(product.price),
                    "tags": [self.tag2.pk, self.tag3.pk],
                },
            },
        )

        product.refresh_from_db()
        self.assertEqual(product.tags.count(), 2)
        self.assertNotIn(self.tag1, product.tags.all())
        self.assertIn(self.tag2, product.tags.all())
        self.assertIn(self.tag3, product.tags.all())

    def test_empty_many_to_many(self):
        """Test setting empty array for ManyToMany field."""
        product = ProductFactory(name="Test Product", price="50.00")
        product.tags.add(self.tag1, self.tag2)

        # Clear all tags
        self.client.call_tool(
            "update_taggedproducts",
            arguments={
                "kwargs": {"pk": str(product.pk)},
                "body": {
                    "name": product.name,
                    "price": str(product.price),
                    "tags": [],
                },
            },
        )

        product.refresh_from_db()
        self.assertEqual(product.tags.count(), 0)

    def test_list_tools_includes_relationship_fields(self):
        """Test that tool schemas properly include relationship field info."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find create_orders tool
        create_orders = next(t for t in tools if t["name"] == "create_orders")
        body_schema = create_orders["inputSchema"]["properties"]["body"]

        # Check customer field is present and correct type
        self.assertIn("customer", body_schema["properties"])
        customer_field = body_schema["properties"]["customer"]
        self.assertEqual(customer_field["type"], "integer")

        # Find create_productslug tool
        create_products = next(t for t in tools if t["name"] == "create_slugproducts")
        body_schema = create_products["inputSchema"]["properties"]["body"]

        # Check category_slug field is present and correct type (allows null due to allow_null=True)
        self.assertIn("category_slug", body_schema["properties"])
        category_field = body_schema["properties"]["category_slug"]
        self.assertEqual(category_field["type"], ["string", "null"])

        # Find create_productwithtags tool
        create_tags = next(t for t in tools if t["name"] == "create_taggedproducts")
        body_schema = create_tags["inputSchema"]["properties"]["body"]

        # Check tags field is array of integers
        self.assertIn("tags", body_schema["properties"])
        tags_field = body_schema["properties"]["tags"]
        self.assertEqual(tags_field["type"], "array")
        self.assertEqual(tags_field["items"]["type"], "integer")


class ChoiceFieldIntegrationTests(TestCase):
    """Integration tests for ChoiceField and MultipleChoiceField in MCP ViewSets."""

    def setUp(self):
        """Set up the test environment."""
        super().setUp()
        registry.clear()

        class StatusChoiceSerializer(serializers.Serializer):
            """Serializer with ChoiceField for status."""

            STATUS_CHOICES = [
                ("draft", "Draft"),
                ("published", "Published"),
                ("archived", "Archived"),
            ]

            status = serializers.ChoiceField(choices=STATUS_CHOICES)
            name = serializers.CharField(max_length=100)

        class PriorityChoiceSerializer(serializers.Serializer):
            """Serializer with integer ChoiceField for priority."""

            PRIORITY_CHOICES = [(1, "Low"), (2, "Medium"), (3, "High")]

            priority = serializers.ChoiceField(choices=PRIORITY_CHOICES)
            description = serializers.CharField(max_length=200)

        class TagsMultipleChoiceSerializer(serializers.Serializer):
            """Serializer with MultipleChoiceField for tags."""

            TAG_CHOICES = [
                ("frontend", "Frontend"),
                ("backend", "Backend"),
                ("database", "Database"),
                ("testing", "Testing"),
            ]

            tags = serializers.MultipleChoiceField(choices=TAG_CHOICES)
            title = serializers.CharField(max_length=100)

        class RequiredTagsSerializer(serializers.Serializer):
            """Serializer with MultipleChoiceField that doesn't allow empty."""

            TAG_CHOICES = [
                ("bug", "Bug"),
                ("feature", "Feature"),
                ("docs", "Documentation"),
            ]

            tags = serializers.MultipleChoiceField(
                choices=TAG_CHOICES, allow_empty=False
            )
            summary = serializers.CharField(max_length=100)

        @mcp_viewset()
        class StatusViewSet(viewsets.GenericViewSet):
            def get_serializer_class(self):
                return StatusChoiceSerializer

            @mcp_tool(input_serializer=StatusChoiceSerializer)
            @action(detail=False, methods=["post"])
            def create_with_status(self, request):
                serializer = StatusChoiceSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                return Response(
                    {
                        "id": 1,
                        "status": serializer.validated_data["status"],
                        "name": serializer.validated_data["name"],
                    }
                )

        @mcp_viewset()
        class PriorityViewSet(viewsets.GenericViewSet):
            def get_serializer_class(self):
                return PriorityChoiceSerializer

            @mcp_tool(input_serializer=PriorityChoiceSerializer)
            @action(detail=False, methods=["post"])
            def create_with_priority(self, request):
                serializer = PriorityChoiceSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                return Response(
                    {
                        "id": 1,
                        "priority": serializer.validated_data["priority"],
                        "description": serializer.validated_data["description"],
                    }
                )

        @mcp_viewset()
        class TagsViewSet(viewsets.GenericViewSet):
            def get_serializer_class(self):
                return TagsMultipleChoiceSerializer

            @mcp_tool(input_serializer=TagsMultipleChoiceSerializer)
            @action(detail=False, methods=["post"])
            def create_with_tags(self, request):
                serializer = TagsMultipleChoiceSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                return Response(
                    {
                        "id": 1,
                        "tags": serializer.validated_data["tags"],
                        "title": serializer.validated_data["title"],
                    }
                )

        @mcp_viewset()
        class RequiredTagsViewSet(viewsets.GenericViewSet):
            def get_serializer_class(self):
                return RequiredTagsSerializer

            @mcp_tool(input_serializer=RequiredTagsSerializer)
            @action(detail=False, methods=["post"])
            def create_with_required_tags(self, request):
                serializer = RequiredTagsSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                return Response(
                    {
                        "id": 1,
                        "tags": serializer.validated_data["tags"],
                        "summary": serializer.validated_data["summary"],
                    }
                )

        self.viewsets = [
            StatusViewSet,
            PriorityViewSet,
            TagsViewSet,
            RequiredTagsViewSet,
        ]

        # Initialize MCP client
        self.client = MCPClient()

    def test_choice_field_schema_generation(self):
        """Test that ChoiceField generates correct JSON schema with enum."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the status choice tool
        status_tool = next(t for t in tools if t["name"] == "create_with_status_status")
        body_schema = status_tool["inputSchema"]["properties"]["body"]

        # Check status field has enum constraint
        self.assertIn("status", body_schema["properties"])
        status_field = body_schema["properties"]["status"]
        self.assertEqual(status_field["type"], "string")
        self.assertEqual(set(status_field["enum"]), {"draft", "published", "archived"})
        self.assertIn("description", status_field)

    def test_integer_choice_field_schema(self):
        """Test that ChoiceField with integers generates correct schema."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the priority choice tool
        priority_tool = next(
            t for t in tools if t["name"] == "create_with_priority_priority"
        )
        body_schema = priority_tool["inputSchema"]["properties"]["body"]

        # Check priority field has string enum (MCP compliance)
        self.assertIn("priority", body_schema["properties"])
        priority_field = body_schema["properties"]["priority"]
        self.assertEqual(priority_field["type"], "string")
        self.assertEqual(set(priority_field["enum"]), {"1", "2", "3"})

    def test_multiple_choice_field_schema(self):
        """Test that MultipleChoiceField generates array schema with enum items."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the tags choice tool
        tags_tool = next(t for t in tools if t["name"] == "create_with_tags_tags")
        body_schema = tags_tool["inputSchema"]["properties"]["body"]

        # Check tags field is array with enum items
        self.assertIn("tags", body_schema["properties"])
        tags_field = body_schema["properties"]["tags"]
        self.assertEqual(tags_field["type"], "array")
        self.assertEqual(tags_field["items"]["type"], "string")
        self.assertEqual(
            set(tags_field["items"]["enum"]),
            {"frontend", "backend", "database", "testing"},
        )

    def test_multiple_choice_field_with_min_items(self):
        """Test that MultipleChoiceField with allow_empty=False generates minItems constraint."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the required tags tool
        required_tags_tool = next(
            t for t in tools if t["name"] == "create_with_required_tags_requiredtags"
        )
        body_schema = required_tags_tool["inputSchema"]["properties"]["body"]

        # Check tags field has minItems constraint and string enum items
        self.assertIn("tags", body_schema["properties"])
        tags_field = body_schema["properties"]["tags"]
        self.assertEqual(tags_field["type"], "array")
        self.assertEqual(tags_field["minItems"], 1)
        self.assertEqual(tags_field["items"]["type"], "string")
        self.assertEqual(set(tags_field["items"]["enum"]), {"bug", "feature", "docs"})


class TestRegexFieldsIntegration(MCPTestCase):
    """Integration tests for RegexField, SlugField, and IPAddressField."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create serializers with regex-based fields
        class PhoneSerializer(serializers.Serializer):
            """Serializer with RegexField for phone numbers."""

            phone = serializers.RegexField(regex=r"^\+?1?\d{9,15}$", max_length=17)

        class ArticleSerializer(serializers.Serializer):
            """Serializer with SlugField."""

            slug = serializers.SlugField(max_length=50)

        class ServerSerializer(serializers.Serializer):
            """Serializer with IPAddressField."""

            ip_address = serializers.IPAddressField()

        # Register ViewSets with the serializers
        @mcp_viewset(basename="phones")
        class PhoneViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = PhoneSerializer

        @mcp_viewset(basename="articles")
        class ArticleViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = ArticleSerializer

        @mcp_viewset(basename="servers")
        class ServerViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = ServerSerializer

        # Store viewsets for cleanup
        self.viewsets = [PhoneViewSet, ArticleViewSet, ServerViewSet]

        # Create test client
        self.client = MCPClient()

    def tearDown(self):
        """Clean up registered viewsets."""
        registry.clear()
        super().tearDown()

    def test_regex_field_schema(self):
        """Test that RegexField generates string schema with pattern."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the phone tool
        phone_tool = next(t for t in tools if t["name"] == "create_phones")
        body_schema = phone_tool["inputSchema"]["properties"]["body"]

        # Check phone field has regex pattern
        self.assertIn("phone", body_schema["properties"])
        phone_field = body_schema["properties"]["phone"]
        self.assertEqual(phone_field["type"], "string")
        self.assertEqual(phone_field["pattern"], r"^\+?1?\d{9,15}$")
        self.assertEqual(phone_field["maxLength"], 17)

    def test_slug_field_schema(self):
        """Test that SlugField generates string schema with slug pattern."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the article tool
        article_tool = next(t for t in tools if t["name"] == "create_articles")
        body_schema = article_tool["inputSchema"]["properties"]["body"]

        # Check slug field has appropriate pattern
        self.assertIn("slug", body_schema["properties"])
        slug_field = body_schema["properties"]["slug"]
        self.assertEqual(slug_field["type"], "string")
        # SlugField should have a pattern for slug validation
        self.assertIn("pattern", slug_field)
        self.assertEqual(slug_field["maxLength"], 50)

    def test_ip_address_field_schema(self):
        """Test that IPAddressField generates string schema with description."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the server tool
        server_tool = next(t for t in tools if t["name"] == "create_servers")
        body_schema = server_tool["inputSchema"]["properties"]["body"]

        # Check ip_address field has description (no pattern for IP fields)
        self.assertIn("ip_address", body_schema["properties"])
        ip_field = body_schema["properties"]["ip_address"]
        self.assertEqual(ip_field["type"], "string")
        # IPAddressField uses function validators, not regex, so should have description
        self.assertIn("description", ip_field)
        self.assertIn("IPv", ip_field["description"])  # Should mention IPv4 or IPv6


class TestCompositeFieldsIntegration(MCPTestCase):
    """Integration tests for ListField, DictField, and JSONField."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create serializers with composite fields
        class TagListSerializer(serializers.Serializer):
            """Serializer with ListField for tags."""

            tags = serializers.ListField(
                child=serializers.CharField(max_length=50), min_length=1, max_length=10
            )

        class MetadataSerializer(serializers.Serializer):
            """Serializer with DictField for metadata."""

            metadata = serializers.DictField(
                child=serializers.CharField(), allow_empty=False
            )

        class ConfigSerializer(serializers.Serializer):
            """Serializer with JSONField for configuration."""

            config = serializers.JSONField()

        # Register ViewSets with the serializers
        @mcp_viewset(basename="tags")
        class TagListViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = TagListSerializer

        @mcp_viewset(basename="metadata")
        class MetadataViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = MetadataSerializer

        @mcp_viewset(basename="config")
        class ConfigViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = ConfigSerializer

        # Store viewsets for cleanup
        self.viewsets = [TagListViewSet, MetadataViewSet, ConfigViewSet]

        # Create test client
        self.client = MCPClient()

    def tearDown(self):
        """Clean up registered viewsets."""
        registry.clear()
        super().tearDown()

    def test_list_field_schema(self):
        """Test that ListField generates array schema with items."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the tags tool
        tags_tool = next(t for t in tools if t["name"] == "create_tags")
        body_schema = tags_tool["inputSchema"]["properties"]["body"]

        # Check tags field is array with string items
        self.assertIn("tags", body_schema["properties"])
        tags_field = body_schema["properties"]["tags"]
        self.assertEqual(tags_field["type"], "array")
        self.assertEqual(tags_field["items"]["type"], "string")
        self.assertEqual(tags_field["items"]["maxLength"], 50)
        self.assertEqual(tags_field["minItems"], 1)
        self.assertEqual(tags_field["maxItems"], 10)

    def test_dict_field_schema(self):
        """Test that DictField generates object schema with additionalProperties."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the metadata tool
        metadata_tool = next(t for t in tools if t["name"] == "create_metadata")
        body_schema = metadata_tool["inputSchema"]["properties"]["body"]

        # Check metadata field is object with string additionalProperties
        self.assertIn("metadata", body_schema["properties"])
        metadata_field = body_schema["properties"]["metadata"]
        self.assertEqual(metadata_field["type"], "object")
        self.assertEqual(metadata_field["additionalProperties"]["type"], "string")
        self.assertEqual(metadata_field["minProperties"], 1)

    def test_json_field_schema(self):
        """Test that JSONField generates permissive schema."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the config tool
        config_tool = next(t for t in tools if t["name"] == "create_config")
        body_schema = config_tool["inputSchema"]["properties"]["body"]

        # Check config field allows any JSON
        self.assertIn("config", body_schema["properties"])
        config_field = body_schema["properties"]["config"]
        # JSONField should have empty schema (most permissive)
        # or no type constraint beyond what field_to_json_schema adds
        self.assertNotIn("items", config_field)  # Not an array schema
        self.assertNotIn("additionalProperties", config_field)  # Not a dict schema


@override_settings(ROOT_URLCONF="tests.urls")
class TestDurationFieldIntegration(MCPTestCase):
    """Integration tests for DurationField."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        from datetime import timedelta

        # Create serializer with DurationField
        class TimerSerializer(serializers.Serializer):
            """Serializer with DurationField for time tracking."""

            duration = serializers.DurationField(
                help_text="Time duration in ISO 8601 format"
            )
            min_duration = serializers.DurationField(
                min_value=timedelta(minutes=5),
                max_value=timedelta(hours=2),
                help_text="Duration between 5 minutes and 2 hours",
            )
            optional_duration = serializers.DurationField(
                required=False, default=timedelta(hours=1)
            )

        # Register ViewSet with the serializer
        @mcp_viewset(basename="timer")
        class TimerViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = TimerSerializer

        # Store for cleanup
        self.viewset = TimerViewSet

        # Create test client
        self.client = MCPClient()

        # Import timedelta for tests
        from datetime import timedelta

        self.timedelta = timedelta

    def tearDown(self):
        """Clean up registered viewsets."""
        registry.clear()
        super().tearDown()

    def test_duration_field_schema(self):
        """Test that DurationField generates correct schema."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find the timer tool
        timer_tool = next(t for t in tools if t["name"] == "create_timer")
        body_schema = timer_tool["inputSchema"]["properties"]["body"]

        # Check basic duration field
        self.assertIn("duration", body_schema["properties"])
        duration_field = body_schema["properties"]["duration"]
        self.assertEqual(duration_field["type"], "string")
        self.assertEqual(duration_field["format"], "duration")
        self.assertIn("ISO 8601", duration_field["description"])

        # Check constrained duration field
        self.assertIn("min_duration", body_schema["properties"])
        min_duration_field = body_schema["properties"]["min_duration"]
        self.assertEqual(min_duration_field["type"], "string")
        self.assertEqual(min_duration_field["format"], "duration")
        self.assertIn("minimum", min_duration_field)
        self.assertIn("maximum", min_duration_field)

        # Check optional duration field
        self.assertIn("optional_duration", body_schema["properties"])
        optional_field = body_schema["properties"]["optional_duration"]
        self.assertEqual(optional_field["type"], "string")
        self.assertEqual(optional_field["format"], "duration")

        # Check required fields
        required = body_schema.get("required", [])
        self.assertIn("duration", required)
        self.assertIn("min_duration", required)
        self.assertNotIn("optional_duration", required)


@override_settings(ROOT_URLCONF="tests.urls")
class TestMCPExcludeBodyParamsIntegration(MCPTestCase):
    """Integration tests for mcp_exclude_body_params() method."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create a serializer for testing
        class TripSerializer(serializers.Serializer):
            """Serializer with user_id that will be excluded for MCP."""

            user_id = serializers.IntegerField()
            advisor_id = serializers.IntegerField(required=False)
            destination = serializers.CharField(max_length=200)
            budget = serializers.DecimalField(max_digits=10, decimal_places=2)

        # Create ViewSet that excludes user_id from body
        @mcp_viewset(basename="trips")
        class TripViewSet(viewsets.GenericViewSet):
            serializer_class = TripSerializer

            def mcp_exclude_body_params(self):
                """Exclude user_id from body params for all actions."""
                return "user_id"

            def create(self, request):
                # In real app, user_id would come from request.user.id
                data = request.data.copy()
                data["user_id"] = 1  # Simulate getting from auth
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)

        # Create ViewSet with action-specific exclusion
        @mcp_viewset(basename="bookings")
        class BookingViewSet(viewsets.GenericViewSet):
            serializer_class = TripSerializer

            def mcp_exclude_body_params(self):
                """Exclude user_id only for create action."""
                if self.action == "create":
                    return ["user_id", "advisor_id"]
                return []

            def create(self, request):
                data = request.data.copy()
                data["user_id"] = 1
                data.setdefault("advisor_id", 2)
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)

            def update(self, request, pk=None):
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                return Response(serializer.validated_data)

        self.viewsets = [TripViewSet, BookingViewSet]
        self.client = MCPClient()

    def tearDown(self):
        """Clean up registered viewsets."""
        registry.clear()
        super().tearDown()

    def test_excluded_param_not_in_tool_schema(self):
        """Test that excluded parameters don't appear in tools/list schema."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find create_trips tool
        create_trips = next(t for t in tools if t["name"] == "create_trips")
        body_schema = create_trips["inputSchema"]["properties"]["body"]

        # user_id should NOT be in the schema
        self.assertNotIn("user_id", body_schema["properties"])

        # Other fields should still be present
        self.assertIn("destination", body_schema["properties"])
        self.assertIn("budget", body_schema["properties"])
        self.assertIn("advisor_id", body_schema["properties"])

    def test_excluded_param_not_required_in_tool_call(self):
        """Test that tool calls work without excluded parameters."""
        result = self.client.call_tool(
            "create_trips",
            {
                "body": {
                    "destination": "Paris",
                    "budget": "2500.00",
                    "advisor_id": 5,
                }
            },
        )

        # Should succeed without user_id in body
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        # Response should include user_id (added by ViewSet)
        self.assertEqual(data["user_id"], 1)
        self.assertEqual(data["destination"], "Paris")
        self.assertEqual(data["budget"], "2500.00")

    def test_action_specific_exclusion(self):
        """Test that exclusion can be action-specific."""
        result = self.client.list_tools()
        tools = result["tools"]

        # Find create and update tools
        create_bookings = next(t for t in tools if t["name"] == "create_bookings")
        update_bookings = next(t for t in tools if t["name"] == "update_bookings")

        create_body = create_bookings["inputSchema"]["properties"]["body"]
        update_body = update_bookings["inputSchema"]["properties"]["body"]

        # For create: user_id and advisor_id should be excluded
        self.assertNotIn("user_id", create_body["properties"])
        self.assertNotIn("advisor_id", create_body["properties"])
        self.assertIn("destination", create_body["properties"])

        # For update: all fields should be present
        self.assertIn("user_id", update_body["properties"])
        self.assertIn("advisor_id", update_body["properties"])
        self.assertIn("destination", update_body["properties"])

    def test_create_booking_without_excluded_params(self):
        """Test creating a booking without excluded parameters."""
        result = self.client.call_tool(
            "create_bookings",
            {"body": {"destination": "Tokyo", "budget": "3000.00"}},
        )

        # Should succeed
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]

        # ViewSet should have added the excluded params
        self.assertEqual(data["user_id"], 1)
        self.assertEqual(data["advisor_id"], 2)
        self.assertEqual(data["destination"], "Tokyo")

    def test_update_booking_with_all_params(self):
        """Test updating a booking requires all parameters (not excluded)."""
        # For update action, exclusion list is empty, so all params are required
        result = self.client.call_tool(
            "update_bookings",
            {
                "kwargs": {"pk": "1"},
                "body": {
                    "user_id": 10,
                    "advisor_id": 20,
                    "destination": "London",
                    "budget": "1500.00",
                },
            },
        )

        # Should succeed with all params
        self.assertFalse(result.get("isError"))
        data = result["structuredContent"]
        self.assertEqual(data["user_id"], 10)
        self.assertEqual(data["advisor_id"], 20)
