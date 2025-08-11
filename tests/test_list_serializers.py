"""Tests for list input serializers (many=True support)."""

import unittest
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.test import TestCase, override_settings
from djangorestframework_mcp.decorators import mcp_viewset, mcp_tool
from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.schema import generate_body_schema, get_serializer_schema
from djangorestframework_mcp.types import MCPTool
from djangorestframework_mcp.test import MCPClient


class SimpleItemSerializer(serializers.Serializer):
    """Simple serializer for testing list inputs."""
    name = serializers.CharField(max_length=100)
    value = serializers.IntegerField()
    is_active = serializers.BooleanField(default=True)


class SimpleItemListSerializer(serializers.ListSerializer):
    """List serializer for testing list inputs."""
    child = SimpleItemSerializer()


class TestListSerializerSchemaGeneration(unittest.TestCase):
    """Test schema generation for list serializers."""
    
    def setUp(self):
        """Set up test fixtures."""
        registry.clear()
    
    def test_generate_schema_from_single_serializer_class(self):
        """Test schema generation from a regular serializer class."""
        schema = get_serializer_schema(SimpleItemSerializer())
        
        self.assertEqual(schema['type'], 'object')
        self.assertIn('properties', schema)
        self.assertIn('name', schema['properties'])
        self.assertIn('value', schema['properties'])
        self.assertIn('is_active', schema['properties'])
        
        # Check field types
        self.assertEqual(schema['properties']['name']['type'], 'string')
        self.assertEqual(schema['properties']['value']['type'], 'integer')
        self.assertEqual(schema['properties']['is_active']['type'], 'boolean')
    
    
    def test_generate_schema_from_list_serializer_listserializer_subclass(self):
        """Test schema generation from ListSerializer subclass."""
        # Create a tool with a ListSerializer to test list schema generation
        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            pass
        
        tool = MCPTool(
            name='test_tool',
            viewset_class=TestViewSet,
            action='create'
        )
        tool.input_serializer = SimpleItemListSerializer
        
        body_info = generate_body_schema(tool)
        schema = body_info['schema']
        
        # Should be a list schema (JSON Schema type 'array')
        self.assertEqual(schema['type'], 'array')
        self.assertIn('items', schema)
        
        # Items should have the structure of SimpleItemSerializer
        item_schema = schema['items']
        self.assertEqual(item_schema['type'], 'object')
        self.assertIn('properties', item_schema)
        self.assertIn('name', item_schema['properties'])
        self.assertIn('value', item_schema['properties'])
        self.assertIn('is_active', item_schema['properties'])
    
    def test_generate_body_schema_with_list_input_serializer(self):
        """Test generate_body_schema with list input serializer."""
        
        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=['post'])
            def bulk_create(self, request):
                return Response({'created': len(request.data)})
        
        # Get the registered tool
        tools = registry.get_all_tools()
        bulk_create_tool = next(t for t in tools if t.action == 'bulk_create')
        
        # Generate body schema
        body_info = generate_body_schema(bulk_create_tool)
        
        # Should have list schema (JSON Schema type 'array')
        self.assertIsNotNone(body_info['schema'])
        self.assertEqual(body_info['schema']['type'], 'array')
        self.assertIn('items', body_info['schema'])
        
        # Items should be objects with our expected properties
        item_schema = body_info['schema']['items']
        self.assertEqual(item_schema['type'], 'object')
        self.assertIn('name', item_schema['properties'])
        self.assertIn('value', item_schema['properties'])
    
    def test_generate_body_schema_with_single_input_serializer(self):
        """Test generate_body_schema with single input serializer (for comparison)."""
        
        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemSerializer)
            @action(detail=False, methods=['post'])
            def single_create(self, request):
                return Response({'created': 1})
        
        # Get the registered tool
        tools = registry.get_all_tools()
        single_create_tool = next(t for t in tools if t.action == 'single_create')
        
        # Generate body schema
        body_info = generate_body_schema(single_create_tool)
        
        # Should have object schema
        self.assertIsNotNone(body_info['schema'])
        self.assertEqual(body_info['schema']['type'], 'object')
        self.assertIn('properties', body_info['schema'])
        self.assertIn('name', body_info['schema']['properties'])


@override_settings(ROOT_URLCONF='tests.urls')
class TestListSerializerIntegration(TestCase):
    """Integration tests for list serializers with actual MCP tool execution."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Initialize MCP client for all tests
        self.client = MCPClient()
        registry.clear()
    
    def test_viewset_with_mixed_single_and_list_endpoints(self):
        """Test ViewSet with both single item and list endpoints."""
        
        @mcp_viewset()
        class ItemViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemSerializer)
            @action(detail=False, methods=['post'])
            def create_single(self, request):
                return Response({
                    'message': 'Single item created',
                    'item': request.data
                })
            
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=['post'])
            def create_bulk(self, request):
                return Response({
                    'message': f'Bulk created {len(request.data)} items',
                    'items': request.data
                })
        
        # Test single item endpoint
        single_result = self.client.call_tool('create_single_item', {
            'body': {
                'name': 'Test Item',
                'value': 42,
                'is_active': True
            }
        })
        
        self.assertFalse(single_result.get('isError'))
        structured_data = single_result['structuredContent']
        self.assertEqual(structured_data['message'], 'Single item created')
        self.assertEqual(structured_data['item']['name'], 'Test Item')
        
        # Test bulk endpoint
        bulk_result = self.client.call_tool('create_bulk_item', {
            'body': [
                {'name': 'Item 1', 'value': 10, 'is_active': True},
                {'name': 'Item 2', 'value': 20, 'is_active': False},
                {'name': 'Item 3', 'value': 30, 'is_active': True}
            ]
        })
        
        self.assertFalse(bulk_result.get('isError'))
        structured_data = bulk_result['structuredContent']
        self.assertEqual(structured_data['message'], 'Bulk created 3 items')
        self.assertEqual(len(structured_data['items']), 3)
        self.assertEqual(structured_data['items'][0]['name'], 'Item 1')
        self.assertEqual(structured_data['items'][1]['value'], 20)
    
    def test_list_endpoint_tool_schema_in_tools_list(self):
        """Test that list endpoints show correct schema in tools list."""
        
        @mcp_viewset()
        class BulkViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=['post'])
            def bulk_operation(self, request):
                return Response({'processed': len(request.data)})
        
        # List all tools and find our bulk operation
        tools_result = self.client.list_tools()
        tools_list = tools_result['tools']
        bulk_tool = next(t for t in tools_list if t['name'] == 'bulk_operation_bulk')
        
        # Check the input schema
        input_schema = bulk_tool['inputSchema']
        self.assertIn('body', input_schema['properties'])
        
        body_schema = input_schema['properties']['body']
        self.assertEqual(body_schema['type'], 'array')
        self.assertIn('items', body_schema)
        
        # Items should have the expected object structure
        item_schema = body_schema['items']
        self.assertEqual(item_schema['type'], 'object')
        self.assertIn('name', item_schema['properties'])
        self.assertIn('value', item_schema['properties'])
        self.assertIn('is_active', item_schema['properties'])
    
    def test_empty_list_input(self):
        """Test that empty list input works correctly."""
        
        @mcp_viewset()
        class EmptyTestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=['post'])
            def process_items(self, request):
                return Response({'count': len(request.data)})
        
        # Test with empty list
        result = self.client.call_tool('process_items_emptytest', {
            'body': []
        })
        
        self.assertFalse(result.get('isError'))
        structured_data = result['structuredContent']
        self.assertEqual(structured_data['count'], 0)
    
    def test_list_input_with_validation_errors(self):
        """Test that validation errors work correctly with list inputs."""
        
        class StrictSerializer(serializers.Serializer):
            name = serializers.CharField(max_length=5, required=True)  # Very short for testing
            value = serializers.IntegerField(min_value=0, required=True)
        
        class StrictListSerializer(serializers.ListSerializer):
            child = StrictSerializer()
        
        @mcp_viewset()
        class ValidationViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=StrictListSerializer)
            @action(detail=False, methods=['post'])
            def validate_items(self, request):
                serializer = StrictSerializer(data=request.data, many=True)
                if serializer.is_valid():
                    return Response({'valid': True, 'data': serializer.data})
                else:
                    return Response({'valid': False, 'errors': serializer.errors}, 
                                  status=status.HTTP_400_BAD_REQUEST)
        
        # Test with invalid data (name too long, negative value)
        result = self.client.call_tool('validate_items_validation', {
            'body': [
                {'name': 'ValidName', 'value': 10},
                {'name': 'TooLongName', 'value': -5}  # Invalid data
            ]
        })
        
        # Should get a validation error
        self.assertTrue(result.get('isError'))
        error_text = result['content'][0]['text']
        self.assertIn('ViewSet returned error', error_text)


class TestInstanceRejection(unittest.TestCase):
    """Test that serializer instances are properly rejected with helpful errors."""
    
    def setUp(self):
        """Set up test fixtures."""
        registry.clear()
    
    def test_decorator_rejects_serializer_instance(self):
        """Test that @mcp_tool decorator rejects serializer instances."""
        
        with self.assertRaises(ValueError) as context:
            @mcp_viewset()
            class TestViewSet(viewsets.GenericViewSet):
                @mcp_tool(input_serializer=SimpleItemSerializer())  # Instance, not class
                @action(detail=False, methods=['post'])
                def bad_action(self, request):
                    return Response({})
        
        error_msg = str(context.exception)
        self.assertIn("must be a serializer class, not an instance", error_msg)
    
    def test_decorator_rejects_many_true_instance(self):
        """Test that @mcp_tool decorator rejects many=True instances."""
        
        with self.assertRaises(ValueError) as context:
            @mcp_viewset()
            class TestViewSet(viewsets.GenericViewSet):
                @mcp_tool(input_serializer=SimpleItemSerializer(many=True))  # Instance, not class
                @action(detail=False, methods=['post'])
                def bad_action(self, request):
                    return Response({})
        
        error_msg = str(context.exception)
        self.assertIn("must be a serializer class, not an instance", error_msg)
    


class TestNestedListSerializers(unittest.TestCase):
    """Test list serializers with nested structures."""
    
    def setUp(self):
        """Set up test fixtures."""
        registry.clear()
    
    def test_nested_serializer_with_list(self):
        """Test serializer with nested lists."""
        
        class NestedItemSerializer(serializers.Serializer):
            id = serializers.IntegerField()
            name = serializers.CharField()
        
        class ContainerSerializer(serializers.Serializer):
            title = serializers.CharField()
            items = NestedItemSerializer(many=True)
        
        schema = get_serializer_schema(ContainerSerializer())
        
        self.assertEqual(schema['type'], 'object')
        self.assertIn('title', schema['properties'])
        self.assertIn('items', schema['properties'])
        
        # Items should be a list (JSON Schema type 'array')
        items_schema = schema['properties']['items']
        self.assertEqual(items_schema['type'], 'array')
        self.assertIn('items', items_schema)
        
        # List items should be objects with id and name
        item_schema = items_schema['items']
        self.assertEqual(item_schema['type'], 'object')
        self.assertIn('id', item_schema['properties'])
        self.assertIn('name', item_schema['properties'])


if __name__ == '__main__':
    unittest.main()