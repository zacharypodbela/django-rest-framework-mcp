"""Integration tests for MCP functionality."""

from django.test import TestCase, override_settings
from djangorestframework_mcp.test import MCPTestCase
from .models import Customer


@override_settings(ROOT_URLCONF='tests.urls')
class MCPToolDiscoveryTests(MCPTestCase):
    """Test MCP tool discovery."""
    
    def test_list_tools(self):
        """Test that MCP tools are properly listed."""
        tools = self.list_tools()
        
        # Check that we have tools
        self.assertGreater(len(tools), 0)
        
        # Find customer tools
        customer_tools = [t for t in tools if 'customers' in t['name']]
        self.assertEqual(len(customer_tools), 6)  # CRUD operations
        
        # Check tool names
        tool_names = {t['name'] for t in customer_tools}
        expected_names = {
            'list_customers',
            'retrieve_customers', 
            'create_customers',
            'update_customers',
            'partial_update_customers',
            'destroy_customers'
        }
        self.assertEqual(tool_names, expected_names)
        
        # Check that tools have schemas
        for tool in customer_tools:
            self.assertIn('inputSchema', tool)
            self.assertIn('type', tool['inputSchema'])
            self.assertEqual(tool['inputSchema']['type'], 'object')


@override_settings(ROOT_URLCONF='tests.urls')
class MCPToolExecutionTests(MCPTestCase):
    """Test MCP tool execution."""
    
    def setUp(self):
        super().setUp()
        # Create test data
        self.customer1 = Customer.objects.create(
            name="Alice Smith",
            email="alice@example.com",
            age=30,
            is_active=True
        )
        self.customer2 = Customer.objects.create(
            name="Bob Jones",
            email="bob@example.com",
            age=25,
            is_active=False
        )
    
    def test_list_customers(self):
        """Test listing customers via MCP."""
        result = self.call_tool('list_customers')
        
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        
        # Check customer data
        emails = {c['email'] for c in result}
        self.assertEqual(emails, {'alice@example.com', 'bob@example.com'})
    
    def test_retrieve_customer(self):
        """Test retrieving a specific customer via MCP."""
        result = self.call_tool('retrieve_customers', {
            'kwargs': {'pk': str(self.customer1.id)}
        })
        
        self.assertEqual(result['name'], 'Alice Smith')
        self.assertEqual(result['email'], 'alice@example.com')
        self.assertEqual(result['age'], 30)
        self.assertTrue(result['is_active'])
    
    def test_create_customer(self):
        """Test creating a customer via MCP."""
        data = {
            'body': {
                'name': 'Charlie Brown',
                'email': 'charlie@example.com',
                'age': 35,
                'is_active': True
            }
        }
        
        result = self.call_tool('create_customers', data)
        
        # Check response
        self.assertEqual(result['name'], 'Charlie Brown')
        self.assertEqual(result['email'], 'charlie@example.com')
        
        # Verify in database
        customer = Customer.objects.get(email='charlie@example.com')
        self.assertEqual(customer.name, 'Charlie Brown')
        self.assertEqual(customer.age, 35)
    
    def test_update_customer(self):
        """Test updating a customer via MCP."""
        data = {
            'kwargs': {'pk': str(self.customer1.id)},
            'body': {
                'name': 'Alice Johnson',
                'email': 'alice.johnson@example.com',
                'age': 31,
                'is_active': False
            }
        }
        
        result = self.call_tool('update_customers', data)
        
        # Check response
        self.assertEqual(result['name'], 'Alice Johnson')
        self.assertEqual(result['email'], 'alice.johnson@example.com')
        
        # Verify in database
        self.customer1.refresh_from_db()
        self.assertEqual(self.customer1.name, 'Alice Johnson')
        self.assertEqual(self.customer1.age, 31)
        self.assertFalse(self.customer1.is_active)
    
    def test_partial_update_customer(self):
        """Test partially updating a customer via MCP."""
        data = {
            'kwargs': {'pk': str(self.customer2.id)},
            'body': {
                'is_active': True
            }
        }
        
        result = self.call_tool('partial_update_customers', data)
        
        # Check response - other fields unchanged
        self.assertEqual(result['name'], 'Bob Jones')
        self.assertEqual(result['email'], 'bob@example.com')
        self.assertTrue(result['is_active'])
        
        # Verify in database
        self.customer2.refresh_from_db()
        self.assertTrue(self.customer2.is_active)
        self.assertEqual(self.customer2.name, 'Bob Jones')  # Unchanged
    
    def test_destroy_customer(self):
        """Test deleting a customer via MCP."""
        initial_count = Customer.objects.count()
        
        result = self.call_tool('destroy_customers', {
            'kwargs': {'pk': str(self.customer1.id)}
        })
        
        # Check response
        self.assertIn('message', result)
        
        # Verify deletion
        self.assertEqual(Customer.objects.count(), initial_count - 1)
        self.assertFalse(Customer.objects.filter(id=self.customer1.id).exists())
    
    def test_error_handling_not_found(self):
        """Test error handling for non-existent customer."""
        with self.assertRaises(Exception) as context:
            self.call_tool('retrieve_customers', {
                'kwargs': {'pk': '99999'}
            })
        
        # DRF returns "No Customer matches the given query"
        error_msg = str(context.exception).lower()
        self.assertTrue(
            'not found' in error_msg or 'no customer matches' in error_msg,
            f"Expected error message about not found, got: {error_msg}"
        )
    
    def test_error_handling_validation(self):
        """Test error handling for validation errors."""
        # Try to create customer with duplicate email
        data = {
            'body': {
                'name': 'Duplicate',
                'email': self.customer1.email,  # Duplicate email
                'age': 40
            }
        }
        
        with self.assertRaises(Exception) as context:
            self.call_tool('create_customers', data)
        
        # Check for validation-related error messages
        error_msg = str(context.exception).lower()
        self.assertTrue(
            'validation' in error_msg or 'already exists' in error_msg or 'unique' in error_msg,
            f"Expected error message about validation, got: {error_msg}"
        )


@override_settings(ROOT_URLCONF='tests.urls')
class MCPProtocolTests(TestCase):
    """Test MCP protocol implementation."""
    
    def setUp(self):
        """Set up test fixtures, ensuring ViewSets are registered."""
        # Import ViewSets to ensure they are registered
        from tests.views import CustomerViewSet, ProductViewSet
        from djangorestframework_mcp.decorators import mcp_viewset
        
        # Re-register ViewSets in case registry was cleared by other tests
        mcp_viewset()(CustomerViewSet)
        mcp_viewset(basename="products")(ProductViewSet)
    
    def test_initialize_request(self):
        """Test MCP initialize request."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'initialize',
            'params': {
                'protocolVersion': '2025-06-18',
                'capabilities': {},
                'clientInfo': {
                    'name': 'test-client',
                    'version': '1.0.0'
                }
            },
            'id': 1
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        self.assertEqual(data['result']['protocolVersion'], '2025-06-18')
        self.assertIn('capabilities', data['result'])
        self.assertIn('serverInfo', data['result'])
    
    def test_tools_list_request(self):
        """Test MCP tools/list request."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/list',
            'params': {},
            'id': 2
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        self.assertIn('tools', data['result'])
        self.assertIsInstance(data['result']['tools'], list)
        
        # Check that we have both customer and product tools
        tool_names = [t['name'] for t in data['result']['tools']]
        self.assertTrue(any('customers' in name for name in tool_names))
        self.assertTrue(any('products' in name for name in tool_names))
    
    def test_tools_list_includes_titles(self):
        """Test that tools/list includes human-readable titles."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/list',
            'params': {},
            'id': 2
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Find a customer list tool and check it has a title
        tools = data['result']['tools']
        list_tool = next((t for t in tools if t['name'] == 'list_customers'), None)
        
        self.assertIsNotNone(list_tool)
        self.assertIn('title', list_tool)
        self.assertEqual(list_tool['title'], 'List Customers')
        
        # Check retrieve tool title
        retrieve_tool = next((t for t in tools if t['name'] == 'retrieve_customers'), None)
        self.assertIsNotNone(retrieve_tool)
        self.assertIn('title', retrieve_tool)
        self.assertEqual(retrieve_tool['title'], 'Get Customer')
        
        # Check create tool title  
        create_tool = next((t for t in tools if t['name'] == 'create_customers'), None)
        self.assertIsNotNone(create_tool)
        self.assertIn('title', create_tool)
        self.assertEqual(create_tool['title'], 'Create Customer')
    
    def test_notification_handling(self):
        """Test proper JSON-RPC notification handling (no response expected)."""
        from django.test import Client
        import json
        
        client = Client()
        
        # Test proper notification (no id field)
        request_data = {
            'jsonrpc': '2.0',
            'method': 'notifications/initialized'
            # No 'id' field - this makes it a notification
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Per JSON-RPC 2.0, notifications should not return any response content
        # We return 204 No Content to indicate successful processing without response
        self.assertEqual(response.status_code, 204)
        self.assertEqual(len(response.content), 0)
    
    def test_parse_error(self):
        """Test JSON-RPC parse error handling."""
        from django.test import Client
        import json
        
        client = Client()
        
        response = client.post(
            '/mcp/',
            data='invalid json{',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], -32700)  # Parse error
        self.assertIn('Parse error', data['error']['message'])
    
    def test_method_not_found(self):
        """Test JSON-RPC method not found error."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'invalid/method',
            'params': {},
            'id': 101
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], -32601)  # Method not found
        self.assertIn('Method not found', data['error']['message'])
    
    def test_tool_not_found(self):
        """Test tool not found error."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'nonexistent_tool',
                'arguments': {}
            },
            'id': 102
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        # Tool not found returns a result with isError: True
        self.assertTrue(data['result']['isError'])
        self.assertIn('Tool not found', data['result']['content'][0]['text'])
    
    def test_missing_required_parameter(self):
        """Test missing required parameter error."""
        from django.test import Client
        import json
        
        client = Client()
        
        # Create test customer first
        Customer.objects.create(
            name="Test Customer",
            email="test@example.com",
            age=30
        )
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'retrieve_customers',
                'arguments': {}  # Missing required 'kwargs' with 'pk'
            },
            'id': 106
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        # Missing parameter returns a result with isError: True
        self.assertTrue(data['result']['isError'])
        error_text = data['result']['content'][0]['text'].lower()
        self.assertTrue('error' in error_text or 'expected' in error_text)
    
    def test_validation_error_missing_fields(self):
        """Test validation error for missing required fields."""
        from django.test import Client
        import json
        
        client = Client()
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'create_customers',
                'arguments': {
                    'body': {
                        'age': 30  # Missing required 'name' and 'email'
                    }
                }
            },
            'id': 104
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        # Validation error returns a result with isError: True
        self.assertTrue(data['result']['isError'])
        error_text = data['result']['content'][0]['text'].lower()
        self.assertTrue('required' in error_text or 'field is required' in error_text)
    
    def test_validation_error_duplicate_email(self):
        """Test validation error for duplicate email."""
        from django.test import Client
        import json
        
        client = Client()
        
        # Create customer with email
        Customer.objects.create(
            name="Existing Customer",
            email="existing@example.com",
            age=25
        )
        
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'create_customers',
                'arguments': {
                    'body': {
                        'name': 'Duplicate User',
                        'email': 'existing@example.com',  # Already exists
                        'age': 40
                    }
                }
            },
            'id': 105
        }
        
        response = client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        # Validation error returns a result with isError: True
        self.assertTrue(data['result']['isError'])
        error_text = data['result']['content'][0]['text'].lower()
        self.assertTrue('already exists' in error_text or 'unique' in error_text)