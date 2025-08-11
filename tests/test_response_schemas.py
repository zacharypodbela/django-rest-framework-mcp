"""
Test response schema consistency across all MCP operations.
"""

import json
from django.test import TestCase, Client
from unittest.mock import Mock, patch
from djangorestframework_mcp.views import MCPView
from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.types import MCPTool


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


