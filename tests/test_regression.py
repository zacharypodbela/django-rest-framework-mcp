"""Regression tests to ensure normal DRF functionality continues to work."""

import base64
import json
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from rest_framework import status

from .factories import CustomerFactory, ProductFactory, TokenFactory, UserFactory
from .models import Customer, Product


class DRFRegressionTests(TestCase):
    """Test suite to ensure normal DRF API functionality continues to work with MCP decorators."""

    def setUp(self):
        """Set up test data and client."""
        self.client = Client()

        # Create test customers
        self.customer1 = CustomerFactory(
            name="Alice Johnson", email="alice@example.com", age=30, is_active=True
        )
        self.customer2 = CustomerFactory(
            name="Bob Smith", email="bob@example.com", age=25, is_active=False
        )

        # Create test products
        self.product1 = ProductFactory(
            name="Laptop",
            description="High-performance laptop",
            price=Decimal("999.99"),
            in_stock=True,
        )
        self.product2 = ProductFactory(
            name="Mouse",
            description="Wireless optical mouse",
            price=Decimal("29.99"),
            in_stock=False,
        )

    def test_customer_list_api(self):
        """Test GET /api/customers/ returns all customers in expected format."""
        url = "/api/customers/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

        # Check first customer data structure
        customer_data = data[0]
        expected_fields = {
            "id",
            "name",
            "email",
            "age",
            "is_active",
            "created_at",
            "updated_at",
        }
        self.assertEqual(set(customer_data.keys()), expected_fields)

        # Verify actual data
        customer_names = {c["name"] for c in data}
        self.assertEqual(customer_names, {"Alice Johnson", "Bob Smith"})

    def test_customer_retrieve_api(self):
        """Test GET /api/customers/{id}/ returns specific customer."""
        url = f"/api/customers/{self.customer1.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["name"], "Alice Johnson")
        self.assertEqual(data["email"], "alice@example.com")
        self.assertEqual(data["age"], 30)
        self.assertTrue(data["is_active"])

    def test_customer_retrieve_not_found(self):
        """Test GET /api/customers/{nonexistent_id}/ returns 404."""
        url = "/api/customers/999/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_create_api(self):
        """Test POST /api/customers/ creates new customer."""
        url = "/api/customers/"
        data = {
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "age": 35,
            "is_active": True,
        }

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response_data = response.json()
        self.assertEqual(response_data["name"], "Charlie Brown")
        self.assertEqual(response_data["email"], "charlie@example.com")
        self.assertIsNotNone(response_data["id"])

        # Verify customer was created in database
        self.assertTrue(Customer.objects.filter(email="charlie@example.com").exists())

    def test_customer_create_validation_error(self):
        """Test POST /api/customers/ with invalid data returns 400."""
        url = "/api/customers/"
        data = {
            "name": "Dave Wilson",
            "email": "invalid-email",  # Invalid email format
            "age": -5,  # Invalid age
        }

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Should contain validation errors
        response_data = response.json()
        self.assertIn("email", response_data)

    def test_customer_update_api(self):
        """Test PUT /api/customers/{id}/ updates customer."""
        url = f"/api/customers/{self.customer1.id}/"
        data = {
            "name": "Alice Johnson Updated",
            "email": "alice.updated@example.com",
            "age": 31,
            "is_active": False,
        }

        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update in database
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, "Alice Johnson Updated")
        self.assertEqual(self.customer1.email, "alice.updated@example.com")
        self.assertEqual(self.customer1.age, 31)
        self.assertFalse(self.customer1.is_active)

    def test_customer_partial_update_api(self):
        """Test PATCH /api/customers/{id}/ partially updates customer."""
        url = f"/api/customers/{self.customer1.id}/"
        data = {
            "age": 32  # Only update age
        }

        response = self.client.patch(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify partial update in database
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.age, 32)
        self.assertEqual(
            self.customer1.name, "Alice Johnson"
        )  # Should remain unchanged
        self.assertEqual(
            self.customer1.email, "alice@example.com"
        )  # Should remain unchanged

    def test_customer_delete_api(self):
        """Test DELETE /api/customers/{id}/ deletes customer."""
        customer_id = self.customer1.id
        url = f"/api/customers/{customer_id}/"

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify customer was deleted
        self.assertFalse(Customer.objects.filter(id=customer_id).exists())

    def test_product_list_api(self):
        """Test GET /api/products/ returns all products in expected format."""
        url = "/api/products/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

        # Check first product data structure
        product_data = data[0]
        expected_fields = {
            "id",
            "name",
            "description",
            "price",
            "in_stock",
            "category",
            "slug",
        }
        self.assertEqual(set(product_data.keys()), expected_fields)

        # Verify actual data
        product_names = {p["name"] for p in data}
        self.assertEqual(product_names, {"Laptop", "Mouse"})

    def test_product_retrieve_api(self):
        """Test GET /api/products/{id}/ returns specific product."""
        url = f"/api/products/{self.product1.id}/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["name"], "Laptop")
        self.assertEqual(data["description"], "High-performance laptop")
        self.assertEqual(data["price"], "999.99")
        self.assertTrue(data["in_stock"])

    def test_product_create_api(self):
        """Test POST /api/products/ creates new product."""
        url = "/api/products/"
        data = {
            "name": "Keyboard",
            "description": "Mechanical keyboard",
            "price": "89.99",
            "in_stock": True,
        }

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response_data = response.json()
        self.assertEqual(response_data["name"], "Keyboard")
        self.assertEqual(response_data["price"], "89.99")
        self.assertIsNotNone(response_data["id"])

        # Verify product was created in database
        self.assertTrue(Product.objects.filter(name="Keyboard").exists())

    def test_product_update_api(self):
        """Test PUT /api/products/{id}/ updates product."""
        url = f"/api/products/{self.product1.id}/"
        data = {
            "name": "Gaming Laptop",
            "description": "High-performance gaming laptop",
            "price": "1299.99",
            "in_stock": False,
        }

        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify update in database
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.name, "Gaming Laptop")
        self.assertEqual(self.product1.price, Decimal("1299.99"))
        self.assertFalse(self.product1.in_stock)

    def test_product_delete_api(self):
        """Test DELETE /api/products/{id}/ deletes product."""
        product_id = self.product1.id
        url = f"/api/products/{product_id}/"

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify product was deleted
        self.assertFalse(Product.objects.filter(id=product_id).exists())

    def test_api_endpoints_without_mcp_request_attribute(self):
        """Test that regular API requests do not have is_mcp_request attribute."""
        url = "/api/customers/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # This test passes if no AttributeError is raised when DRF handles the request
        # The ViewSet should not expect is_mcp_request to be present on regular requests

    def test_content_type_json_handling(self):
        """Test that JSON content-type is handled correctly."""
        url = "/api/customers/"
        data = {"name": "JSON Test User", "email": "json@example.com", "age": 28}

        response = self.client.post(
            url, data=json.dumps(data), content_type="application/json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertEqual(response_data["name"], "JSON Test User")

    def test_content_type_form_handling(self):
        """Test that form-encoded data is handled correctly."""
        url = "/api/customers/"
        data = {"name": "Form Test User", "email": "form@example.com", "age": 27}

        response = self.client.post(url, data)  # Default form encoding

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertEqual(response_data["name"], "Form Test User")

    def test_empty_database_list_returns_empty_array(self):
        """Test that listing resources from empty database returns empty array."""
        # Delete all test data
        Customer.objects.all().delete()
        Product.objects.all().delete()

        # Test customers
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

        # Test products
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_response_headers_are_preserved(self):
        """Test that DRF response headers are preserved."""
        response = self.client.get("/api/customers/")

        # Check for standard DRF headers
        self.assertIn("Content-Type", response.headers)
        self.assertTrue(response.headers["Content-Type"].startswith("application/json"))

    def test_http_methods_routing(self):
        """Test that HTTP method routing works correctly."""
        url = f"/api/customers/{self.customer1.id}/"

        # GET should work
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # PUT should work
        data = {
            "name": "Method Test",
            "email": "method@example.com",
            "age": 25,
            "is_active": True,
        }
        response = self.client.put(
            url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # PATCH should work
        response = self.client.patch(
            url, data=json.dumps({"age": 26}), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # DELETE should work
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


@override_settings(ROOT_URLCONF="tests.urls")
class AuthenticationRegressionTests(TestCase):
    """Regression tests to ensure normal DRF API authentication still works unchanged."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory(
            username="apiuser", email="api@example.com", password="apipass"
        )
        self.token = TokenFactory(user=self.user)

        # Create a staff user for permission tests
        self.staff_user = UserFactory(
            username="staffuser",
            email="staff@example.com",
            password="staffpass",
            is_staff=True,
        )
        self.staff_token = TokenFactory(user=self.staff_user)

    def test_authenticated_viewset_normal_api_with_valid_token(self):
        """Test that authenticated ViewSets work normally via DRF API with valid token."""
        # Make direct API call to ViewSet (not MCP)
        response = self.client.get(
            "/api/auth/authenticated/",  # Direct API endpoint
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        # Should succeed with 200
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Authenticated Item")

    def test_authenticated_viewset_normal_api_without_token(self):
        """Test that authenticated ViewSets reject unauthenticated API requests."""
        # Make direct API call without token
        response = self.client.get("/api/auth/authenticated/")

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response)
        self.assertEqual(response["WWW-Authenticate"], "Token")

    def test_authenticated_viewset_normal_api_with_invalid_token(self):
        """Test that authenticated ViewSets reject invalid tokens via API."""
        response = self.client.get(
            "/api/auth/authenticated/", HTTP_AUTHORIZATION="Token invalid-token-123"
        )

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertIn("Invalid token", data["detail"])

    def test_unauthenticated_viewset_normal_api_works(self):
        """Test that unauthenticated ViewSets work normally via API without token."""
        response = self.client.get("/api/auth/unauthenticated/")

        # Should succeed with 200
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Public Item")

    def test_multiple_auth_viewset_token_auth_via_api(self):
        """Test ViewSet with multiple auth classes works with token via API."""
        response = self.client.get(
            "/api/auth/multipleauth/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data[0]["name"], "Multi-auth Item")

    def test_multiple_auth_viewset_basic_auth_via_api(self):
        """Test ViewSet with multiple auth classes works with basic auth via API."""
        credentials = base64.b64encode(b"apiuser:apipass").decode("ascii")
        response = self.client.get(
            "/api/auth/multipleauth/", HTTP_AUTHORIZATION=f"Basic {credentials}"
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data[0]["name"], "Multi-auth Item")

    def test_custom_auth_viewset_normal_api_works(self):
        """Test custom authentication class works via normal API."""
        response = self.client.get(
            "/api/auth/customauth/",
            HTTP_AUTHORIZATION=f"Custom {self.token.key}",  # Custom keyword
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data[0]["name"], "Custom Auth Item")

    def test_custom_permission_viewset_normal_api_denied(self):
        """Test custom permission class works via normal API."""
        response = self.client.get("/api/auth/custompermission/")

        # Should be denied by custom permission
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Custom permission denied", data["detail"])


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": True})
class BypassAuthenticationRegressionTests(TestCase):
    """Test that bypassing MCP auth doesn't affect normal API authentication."""

    def setUp(self):
        self.user = UserFactory(
            username="regressionuser",
            email="regression@example.com",
            password="regressionpass",
        )
        self.token = TokenFactory(user=self.user)

    def test_bypass_auth_setting_doesnt_affect_normal_api(self):
        """Test that BYPASS_VIEWSET_AUTHENTICATION setting only affects MCP, not normal API."""
        # Even with bypass setting enabled, normal API should still require auth
        response = self.client.get("/api/auth/authenticated/")

        # Should still return 401 for normal API calls
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response)

        # But should work with proper token
        response = self.client.get(
            "/api/auth/authenticated/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )
        self.assertEqual(response.status_code, 200)

    def test_bypass_setting_isolation_from_regular_drf_behavior(self):
        """Test that MCP bypass settings are completely isolated from DRF behavior."""
        # Create a POST request to authenticated endpoint
        response = self.client.post(
            "/api/auth/authenticated/",
            data=json.dumps({"test": "data"}),
            content_type="application/json",
        )

        # Should still require authentication for normal API
        self.assertIn(response.status_code, [401, 405])  # 401 or 405 Method Not Allowed

        # With auth should work (if POST is allowed)
        response = self.client.post(
            "/api/auth/authenticated/",
            data=json.dumps({"test": "data"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.token.key}",
        )

        # Should not be affected by MCP bypass settings
        self.assertNotEqual(response.status_code, 500)  # No server errors


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_PERMISSIONS": True})
class BypassPermissionsRegressionTests(TestCase):
    """Test that bypassing MCP permissions doesn't affect normal API permissions."""

    def setUp(self):
        self.user = UserFactory(
            username="permuser", email="perm@example.com", password="permpass"
        )
        self.token = TokenFactory(user=self.user)

    def test_bypass_permissions_setting_doesnt_affect_normal_api(self):
        """Test that BYPASS_VIEWSET_PERMISSIONS setting only affects MCP, not normal API."""
        # Even with permissions bypass, normal API should still check permissions
        response = self.client.get(
            "/api/auth/authenticated/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        # Should succeed (user is authenticated)
        self.assertEqual(response.status_code, 200)

        # Test without auth - should still fail
        response = self.client.get("/api/auth/authenticated/")
        self.assertEqual(response.status_code, 401)

    def test_bypass_permissions_isolation(self):
        """Test that permission bypass is isolated to MCP requests only."""
        # Test custom permission ViewSet via normal API
        response = self.client.get(
            "/api/auth/custompermission/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        # Should still be denied by normal API (permissions not actually bypassed)
        self.assertEqual(response.status_code, 403)


@override_settings(DJANGORESTFRAMEWORK_MCP={"BYPASS_VIEWSET_AUTHENTICATION": False})
class AuthenticationMiddlewareCompatibilityTests(TestCase):
    """Test compatibility with Django authentication middleware."""

    def setUp(self):
        # Clear and register the test ViewSets
        from djangorestframework_mcp.registry import registry
        from tests.views import AuthenticatedViewSet, MultipleAuthViewSet

        registry.clear()
        registry.register_viewset(AuthenticatedViewSet)
        registry.register_viewset(MultipleAuthViewSet)

        self.user = UserFactory(
            username="middleware",
            email="middleware@example.com",
            password="middlewarepass",
        )
        self.token = TokenFactory(user=self.user)

    def test_session_middleware_compatibility(self):
        """Test that MCP auth works alongside session middleware."""
        # Login user via session
        self.client.login(username="middleware", password="middlewarepass")

        # Normal API should work with session
        response = self.client.get("/api/auth/multipleauth/")
        # May work or may fail depending on CSRF, but shouldn't crash
        self.assertIn(
            response.status_code, [200, 403]
        )  # Either success or CSRF failure

    def test_auth_middleware_doesnt_interfere_with_token_auth(self):
        """Test that auth middleware doesn't interfere with token authentication."""
        response = self.client.get(
            "/api/auth/authenticated/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )

        # Should work normally
        self.assertEqual(response.status_code, 200)

    def test_mcp_and_api_auth_are_independent(self):
        """Test that MCP and API authentication are completely independent."""
        # Set up for both MCP and API requests
        from djangorestframework_mcp.test import MCPClient

        mcp_client = MCPClient()
        mcp_client.defaults["HTTP_AUTHORIZATION"] = f"Token {self.token.key}"

        # Both should work independently
        api_response = self.client.get(
            "/api/auth/authenticated/", HTTP_AUTHORIZATION=f"Token {self.token.key}"
        )
        self.assertEqual(api_response.status_code, 200)

        # MCP should also work
        mcp_result = mcp_client.call_tool("list_authenticated")
        self.assertFalse(mcp_result.get("isError"))

        # They should return the same data but in different formats
        api_data = json.loads(api_response.content)
        mcp_data = mcp_result["structuredContent"]

        self.assertEqual(api_data[0]["name"], mcp_data[0]["name"])
