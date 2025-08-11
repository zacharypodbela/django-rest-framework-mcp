"""Unit tests for test utilities module."""

import json
import unittest
from unittest.mock import Mock, patch
from django.test import TestCase, Client
from djangorestframework_mcp.test import MCPTestCase


class TestMCPTestCase(unittest.TestCase):
    """Test the MCPTestCase utility class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_case = MCPTestCase()
        
        # Mock the setUp to avoid Django setup issues in unit tests
        with patch.object(TestCase, 'setUp'):
            self.test_case.setUp()
    
    def test_initialization(self):
        """Test MCPTestCase initialization."""
        self.assertIsInstance(self.test_case.mcp_client, Client)
        self.assertEqual(self.test_case.mcp_endpoint, '/mcp/')
    
    def test_call_tool_success(self):
        """Test successful tool call."""
        # Mock response with proper MCP format
        mock_response = Mock()
        response_data = {
            'jsonrpc': '2.0',
            'result': {
                'content': [
                    {
                        'type': 'text',
                        'text': '{"data": "result"}'
                    }
                ]
            },
            'id': 1
        }
        mock_response.content = json.dumps(response_data).encode()
        
        # Mock the client post method
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            result = self.test_case.call_tool('test_tool', {'param': 'value'})
            
            self.assertEqual(result, {'data': 'result'})
    
    @patch('djangorestframework_mcp.test.json.loads')
    def test_call_tool_with_error(self, mock_json_loads):
        """Test tool call with MCP error response."""
        mock_response = Mock()
        mock_response.content = b'{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid request"}, "id": 1}'
        
        mock_json_loads.return_value = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32600,
                'message': 'Invalid request'
            },
            'id': 1
        }
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.test_case.call_tool('test_tool')
            
            self.assertIn('MCP error', str(context.exception))
            self.assertIn('Invalid request', str(context.exception))
    
    @patch('djangorestframework_mcp.test.json.loads')
    def test_call_tool_with_execution_error(self, mock_json_loads):
        """Test tool call with tool execution error."""
        mock_response = Mock()
        mock_json_loads.return_value = {
            'jsonrpc': '2.0',
            'result': {
                'content': [
                    {
                        'type': 'text',
                        'text': 'Tool execution failed'
                    }
                ],
                'isError': True
            },
            'id': 1
        }
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.test_case.call_tool('test_tool')
            
            self.assertIn('Tool execution error', str(context.exception))
            self.assertIn('Tool execution failed', str(context.exception))
    
    def test_call_tool_request_structure(self):
        """Test that call_tool creates proper JSON-RPC request."""
        mock_response = Mock()
        mock_response.content = json.dumps({
            'jsonrpc': '2.0',
            'result': {'content': [{'type': 'text', 'text': '{}'}]},
            'id': 1
        }).encode()
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response) as mock_post:
            self.test_case.call_tool('test_tool', {'param1': 'value1', 'param2': 42})
            
            # Verify the POST call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            
            # Check URL (first positional argument)
            self.assertEqual(call_args[0][0], '/mcp/')
            
            # Check content type
            self.assertEqual(call_args[1]['content_type'], 'application/json')
            
            # Parse and check the request data
            request_data = json.loads(call_args[1]['data'])
            
            self.assertEqual(request_data['jsonrpc'], '2.0')
            self.assertEqual(request_data['method'], 'tools/call')
            self.assertEqual(request_data['id'], 1)
            
            params = request_data['params']
            self.assertEqual(params['name'], 'test_tool')
            self.assertEqual(params['arguments'], {'param1': 'value1', 'param2': 42})
    
    def test_call_tool_no_params(self):
        """Test call_tool with no parameters."""
        mock_response = Mock()
        mock_response.content = json.dumps({
            'jsonrpc': '2.0',
            'result': {
                'content': [{'type': 'text', 'text': '{}'}]
            },
            'id': 1
        }).encode()
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response) as mock_post:
            self.test_case.call_tool('test_tool')
            
            # Check that arguments is empty dict
            request_data = json.loads(mock_post.call_args[1]['data'])
            self.assertEqual(request_data['params']['arguments'], {})
    
    def test_call_tool_non_json_response(self):
        """Test call_tool with non-JSON response text."""
        mock_response = Mock()
        response_data = {
            'jsonrpc': '2.0',
            'result': {
                'content': [
                    {
                        'type': 'text',
                        'text': 'plain text response'  # Not JSON
                    }
                ]
            },
            'id': 1
        }
        mock_response.content = json.dumps(response_data).encode()
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            result = self.test_case.call_tool('test_tool')
            
            # Should return text wrapped in dict
            self.assertEqual(result, {'text': 'plain text response'})
    
    @patch('djangorestframework_mcp.test.json.loads')
    def test_list_tools_success(self, mock_json_loads):
        """Test successful tools listing."""
        mock_response = Mock()
        mock_json_loads.return_value = {
            'jsonrpc': '2.0',
            'result': {
                'tools': [
                    {
                        'name': 'tool1',
                        'description': 'Test tool 1',
                        'inputSchema': {'type': 'object'}
                    },
                    {
                        'name': 'tool2',
                        'description': 'Test tool 2',
                        'inputSchema': {'type': 'object'}
                    }
                ]
            },
            'id': 1
        }
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            tools = self.test_case.list_tools()
            
            self.assertEqual(len(tools), 2)
            self.assertEqual(tools[0]['name'], 'tool1')
            self.assertEqual(tools[1]['name'], 'tool2')
    
    def test_list_tools_request_structure(self):
        """Test that list_tools creates proper JSON-RPC request."""
        mock_response = Mock()
        mock_response.content = json.dumps({
            'jsonrpc': '2.0',
            'result': {'tools': []},
            'id': 1
        }).encode()
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response) as mock_post:
            self.test_case.list_tools()
            
            # Verify the POST call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            
            # Check URL (first positional argument) and content type
            self.assertEqual(call_args[0][0], '/mcp/')
            self.assertEqual(call_args[1]['content_type'], 'application/json')
            
            # Parse and check the request data
            request_data = json.loads(call_args[1]['data'])
            
            self.assertEqual(request_data['jsonrpc'], '2.0')
            self.assertEqual(request_data['method'], 'tools/list')
            self.assertEqual(request_data['params'], {})
            self.assertEqual(request_data['id'], 1)
    
    @patch('djangorestframework_mcp.test.json.loads')
    def test_list_tools_with_error(self, mock_json_loads):
        """Test list_tools with MCP error response."""
        mock_response = Mock()
        mock_json_loads.return_value = {
            'jsonrpc': '2.0',
            'error': {
                'code': -32603,
                'message': 'Internal error'
            },
            'id': 1
        }
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            with self.assertRaises(Exception) as context:
                self.test_case.list_tools()
            
            self.assertIn('MCP error', str(context.exception))
            self.assertIn('Internal error', str(context.exception))
    
    @patch('djangorestframework_mcp.test.json.loads')
    def test_list_tools_empty_result(self, mock_json_loads):
        """Test list_tools with empty tools result."""
        mock_response = Mock()
        mock_json_loads.return_value = {
            'jsonrpc': '2.0',
            'result': {},  # No 'tools' key
            'id': 1
        }
        
        with patch.object(self.test_case.mcp_client, 'post', return_value=mock_response):
            tools = self.test_case.list_tools()
            
            # Should return empty list when 'tools' key is missing
            self.assertEqual(tools, [])


class TestMCPTestCaseIntegration(unittest.TestCase):
    """Integration tests for MCPTestCase."""
    
    def test_inheritance(self):
        """Test that MCPTestCase properly inherits from Django TestCase."""
        self.assertTrue(issubclass(MCPTestCase, TestCase))
    
    def test_docstring_and_methods(self):
        """Test MCPTestCase has proper documentation and methods."""
        self.assertIsNotNone(MCPTestCase.__doc__)
        
        # Check required methods exist
        self.assertTrue(hasattr(MCPTestCase, 'call_tool'))
        self.assertTrue(hasattr(MCPTestCase, 'list_tools'))
        self.assertTrue(hasattr(MCPTestCase, 'setUp'))
        
        # Check methods are callable
        self.assertTrue(callable(MCPTestCase.call_tool))
        self.assertTrue(callable(MCPTestCase.list_tools))


if __name__ == '__main__':
    unittest.main()