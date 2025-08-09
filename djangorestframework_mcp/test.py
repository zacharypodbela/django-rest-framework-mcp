"""Test utilities for MCP tools."""

import json
from django.test import TestCase, Client
from typing import Dict, Any, Optional, List


class MCPTestCase(TestCase):
    """Base test case class for testing MCP tools."""
    
    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.mcp_client = Client()
        self.mcp_endpoint = '/mcp/'
    
    def call_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call an MCP tool and return the result.
        
        Args:
            tool_name: Name of the tool to call.
            params: Parameters to pass to the tool.
            
        Returns:
            The tool execution result.
        """
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/call',
            'params': {
                'name': tool_name,
                'arguments': params or {}
            },
            'id': 1
        }
        
        response = self.mcp_client.post(
            self.mcp_endpoint,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        response_data = json.loads(response.content)
        
        # Check for errors
        if 'error' in response_data:
            raise Exception(f"MCP error: {response_data['error']}")
        
        result = response_data.get('result', {})
        
        # Check for tool execution errors
        if result.get('isError'):
            content = result.get('content', [])
            error_text = content[0].get('text', 'Unknown error') if content else 'Unknown error'
            raise Exception(f"Tool execution error: {error_text}")
        
        # Parse the result content
        content = result.get('content', [])
        if content and content[0].get('type') == 'text':
            try:
                return json.loads(content[0].get('text', '{}'))
            except json.JSONDecodeError:
                return {'text': content[0].get('text')}
        
        return result
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available MCP tools.
        
        Returns:
            List of tool definitions.
        """
        request_data = {
            'jsonrpc': '2.0',
            'method': 'tools/list',
            'params': {},
            'id': 1
        }
        
        response = self.mcp_client.post(
            self.mcp_endpoint,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        response_data = json.loads(response.content)
        
        # Check for errors
        if 'error' in response_data:
            raise Exception(f"MCP error: {response_data['error']}")
        
        return response_data.get('result', {}).get('tools', [])