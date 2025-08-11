"""
Test response schema consistency across all MCP operations.
"""

import json
from django.test import TestCase, Client, override_settings
from unittest.mock import Mock, patch
from djangorestframework_mcp.views import MCPView
from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.types import MCPTool
from djangorestframework_mcp.test import MCPTestCase
from .models import Customer


class ResponseSchemaConsistencyTests(TestCase):
    """Test that all responses follow consistent schemas."""
    
    def setUp(self):
        self.client = Client()
        self.view = MCPView()
        
    def test_json_rpc_success_schema(self):
        """Test that all JSON-RPC success responses have consistent schema."""
        # Test initialize
        request_data = {
            'jsonrpc': '2.0',
            'method': 'initialize',
            'params': {},
            'id': 1
        }
        
        response = self.client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        data = json.loads(response.content)
        
        # All success responses MUST have these fields
        self.assertIn('jsonrpc', data)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('result', data)
        self.assertIn('id', data)
        self.assertNotIn('error', data)  # Success should not have error field
        
    def test_json_rpc_error_schema(self):
        """Test that all JSON-RPC error responses have consistent schema."""
        # Test with invalid method
        request_data = {
            'jsonrpc': '2.0',
            'method': 'invalid_method',
            'params': {},
            'id': 2
        }
        
        response = self.client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        data = json.loads(response.content)
        
        # All error responses MUST have these fields
        self.assertIn('jsonrpc', data)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('error', data)
        self.assertIn('id', data)
        self.assertNotIn('result', data)  # Error should not have result field
        
        # Error object must have code and message
        self.assertIn('code', data['error'])
        self.assertIn('message', data['error'])
        self.assertIsInstance(data['error']['code'], int)
        self.assertIsInstance(data['error']['message'], str)
        
    def test_tool_call_success_schema(self):
        """Test that tool call success responses have consistent schema."""
        # Mock a successful tool execution
        with patch.object(registry, 'get_tool_by_name') as mock_get_tool:
            # Create a proper mock viewset class
            mock_viewset_class = Mock()
            mock_viewset_instance = Mock()
            mock_viewset_class.return_value = mock_viewset_instance
            
            # Mock the action method to return a successful response
            mock_response = Mock()
            mock_response.data = {'data': 'test_data'}
            mock_response.status_code = 200
            mock_viewset_instance.list = Mock(return_value=mock_response)
            
            mock_tool = MCPTool(
                name='test_tool',
                viewset_class=mock_viewset_class,
                action='list'
            )
            mock_get_tool.return_value = mock_tool
            
            request_data = {
                'jsonrpc': '2.0',
                'method': 'tools/call',
                'params': {
                    'name': 'test_tool',
                    'arguments': {}
                },
                'id': 3
            }
            
            response = self.client.post(
                '/mcp/',
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            data = json.loads(response.content)
            
            # Check JSON-RPC wrapper
            self.assertIn('result', data)
            result = data['result']
            
            # Tool success MUST have content array
            self.assertIn('content', result)
            self.assertIsInstance(result['content'], list)
            self.assertGreater(len(result['content']), 0)
            
            # Content items must have type and text
            content = result['content'][0]
            self.assertIn('type', content)
            self.assertEqual(content['type'], 'text')
            self.assertIn('text', content)
            
            # Success should NOT have isError field
            self.assertNotIn('isError', result)
                
    def test_tool_call_error_schema(self):
        """Test that tool call error responses have consistent schema."""
        # Mock a failed tool execution
        with patch.object(registry, 'get_tool_by_name') as mock_get_tool:
            mock_tool = MCPTool(
                name='test_tool',
                viewset_class=Mock,
                action='list'
            )
            mock_get_tool.return_value = mock_tool
            
            with patch.object(self.view, 'execute_tool') as mock_execute:
                mock_execute.side_effect = Exception("Test error")
                
                request_data = {
                    'jsonrpc': '2.0',
                    'method': 'tools/call',
                    'params': {
                        'name': 'test_tool',
                        'arguments': {}
                    },
                    'id': 4
                }
                
                response = self.client.post(
                    '/mcp/',
                    data=json.dumps(request_data),
                    content_type='application/json'
                )
                
                data = json.loads(response.content)
                
                # Check JSON-RPC wrapper
                self.assertIn('result', data)
                result = data['result']
                
                # Tool error MUST have content array
                self.assertIn('content', result)
                self.assertIsInstance(result['content'], list)
                self.assertGreater(len(result['content']), 0)
                
                # Content items must have type and text
                content = result['content'][0]
                self.assertIn('type', content)
                self.assertEqual(content['type'], 'text')
                self.assertIn('text', content)
                
                # Error text should have consistent format
                self.assertTrue(content['text'].startswith('Error executing tool:'))
                
                # Error MUST have isError field set to True
                self.assertIn('isError', result)
                self.assertEqual(result['isError'], True)
                
    def test_parse_error_schema(self):
        """Test that parse errors have consistent schema."""
        response = self.client.post(
            '/mcp/',
            data='invalid json',
            content_type='application/json'
        )
        
        data = json.loads(response.content)
        
        # Parse error response schema
        self.assertIn('jsonrpc', data)
        self.assertEqual(data['jsonrpc'], '2.0')
        self.assertIn('error', data)
        self.assertEqual(data['error']['code'], -32700)
        self.assertEqual(data['error']['message'], 'Parse error')
        self.assertIn('id', data)
        self.assertIsNone(data['id'])  # Parse errors have null id
        
    def test_internal_error_schema(self):
        """Test that internal errors have consistent schema."""
        with patch.object(MCPView, 'handle_initialize') as mock_handler:
            mock_handler.side_effect = Exception("Internal test error")
            
            request_data = {
                'jsonrpc': '2.0',
                'method': 'initialize',
                'params': {},
                'id': 5
            }
            
            response = self.client.post(
                '/mcp/',
                data=json.dumps(request_data),
                content_type='application/json'
            )
            
            data = json.loads(response.content)
            
            # Internal error response schema
            self.assertIn('jsonrpc', data)
            self.assertEqual(data['jsonrpc'], '2.0')
            self.assertIn('error', data)
            self.assertEqual(data['error']['code'], -32603)
            self.assertTrue(data['error']['message'].startswith('Internal error:'))
            self.assertIn('id', data)
            self.assertEqual(data['id'], 5)


@override_settings(ROOT_URLCONF='tests.urls')
class StructuredContentTests(MCPTestCase):
    """Test MCP-compliant structured content in tool responses."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Register the CustomerViewSet for testing
        from tests.views import CustomerViewSet
        from djangorestframework_mcp.decorators import mcp_viewset
        registry.clear()
        mcp_viewset()(CustomerViewSet)
    
    def test_structured_content_in_tool_responses(self):
        """Test that tool responses include both content and structuredContent per MCP spec."""
        # Create test customer
        customer = Customer.objects.create(
            name="John Doe",
            email="john@example.com",
            age=30,
            is_active=True
        )
        
        # Call retrieve tool to get structured response
        result = self.call_tool('retrieve_customers', {
            'kwargs': {'pk': str(customer.id)}
        })
        
        # Verify structured content is present and matches expected structure
        self.assertIsInstance(result, dict)
        self.assertIn('name', result)
        self.assertIn('email', result)
        self.assertIn('age', result)
        self.assertEqual(result['name'], 'John Doe')
        self.assertEqual(result['email'], 'john@example.com')
        self.assertEqual(result['age'], 30)
        
        # Now test the raw MCP response structure
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'retrieve_customers',
                'arguments': {
                    'kwargs': {'pk': str(customer.id)}
                }
            },
            'id': 1
        }
        
        response = self.client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        result_data = data['result']
        
        # Verify both content and structuredContent are present
        self.assertIn('content', result_data)
        self.assertIn('structuredContent', result_data)
        
        # Verify content array structure
        content = result_data['content']
        self.assertIsInstance(content, list)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]['type'], 'text')
        self.assertIn('text', content[0])
        
        # Verify structured content matches the actual data
        structured = result_data['structuredContent']
        self.assertIsInstance(structured, dict)
        self.assertEqual(structured['name'], 'John Doe')
        self.assertEqual(structured['email'], 'john@example.com')
        self.assertEqual(structured['age'], 30)
        
        # Verify text content contains JSON representation
        text_content = content[0]['text']
        parsed_text = json.loads(text_content)
        self.assertEqual(parsed_text, structured)  # Should be equivalent
    
    def test_structured_content_with_list_response(self):
        """Test that list responses also include structuredContent."""
        # Create test customers
        Customer.objects.create(name="Alice", email="alice@example.com", age=25)
        Customer.objects.create(name="Bob", email="bob@example.com", age=35)
        
        # Test the raw MCP response structure
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': 'list_customers',
                'arguments': {}
            },
            'id': 1
        }
        
        response = self.client.post(
            '/mcp/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        result_data = data['result']
        
        # Verify both content and structuredContent are present
        self.assertIn('content', result_data)
        self.assertIn('structuredContent', result_data)
        
        # Verify structured content is a list
        structured = result_data['structuredContent']
        self.assertIsInstance(structured, list)
        self.assertEqual(len(structured), 2)
        
        # Verify text content contains JSON representation of the list
        text_content = result_data['content'][0]['text']
        parsed_text = json.loads(text_content)
        self.assertEqual(parsed_text, structured)