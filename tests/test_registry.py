"""Unit tests for registry module."""

import unittest
from unittest.mock import Mock
from rest_framework.viewsets import ModelViewSet
from djangorestframework_mcp.registry import MCPRegistry, registry


class TestMCPRegistry(unittest.TestCase):
    """Test the MCPRegistry class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = MCPRegistry()
        
        # Create mock ViewSet classes
        class MockModel:
            __name__ = 'MockModel'
        
        self.mock_queryset = Mock()
        self.mock_queryset.model = MockModel
        
        class MockViewSet(ModelViewSet):
            queryset = self.mock_queryset
            
            def list(self):
                pass
            
            def retrieve(self):
                pass
            
            def create(self):
                pass
            
            def update(self):
                pass
            
            def partial_update(self):
                pass
            
            def destroy(self):
                pass
        
        self.MockViewSet = MockViewSet
    
    def test_register_viewset_with_default_name(self):
        """Test registering a ViewSet with default name generation."""
        self.registry.register_viewset(self.MockViewSet)
        
        # Check that tools were registered
        tools = self.registry.get_all_tools()
        self.assertEqual(len(tools), 6)  # list, retrieve, create, update, partial_update, destroy
        
        tool_names = [t.name for t in tools]
        self.assertIn('list_mockmodels', tool_names)
        self.assertIn('retrieve_mockmodels', tool_names)
        self.assertIn('create_mockmodels', tool_names)
        self.assertIn('update_mockmodels', tool_names)
        self.assertIn('partial_update_mockmodels', tool_names)
        self.assertIn('destroy_mockmodels', tool_names)
    
    def test_register_viewset_with_custom_name(self):
        """Test registering a ViewSet with a custom base name."""
        self.registry.register_viewset(self.MockViewSet, base_name='custom_name')
        
        # Check that tools were registered with custom base name
        tools = self.registry.get_all_tools()
        tool_names = [t.name for t in tools]
        self.assertIn('list_custom_name', tool_names)
        self.assertIn('retrieve_custom_name', tool_names)
    
    def test_register_viewset_without_queryset(self):
        """Test registering a ViewSet without a queryset."""
        class SimpleViewSet(ModelViewSet):
            def list(self): pass
            def retrieve(self): pass
        
        self.registry.register_viewset(SimpleViewSet)
        
        # Should use class name as fallback
        tools = self.registry.get_all_tools()
        tool_names = [t.name for t in tools]
        self.assertIn('list_simple', tool_names)
        self.assertIn('retrieve_simple', tool_names)
    
    
    
    def test_get_registerable_actions(self):
        """Test that _get_registerable_actions correctly identifies registerable actions."""
        actions = self.registry._get_registerable_actions(self.MockViewSet)
        self.assertEqual(set(actions), {'list', 'retrieve', 'create', 'update', 'partial_update', 'destroy'})
    
    def test_get_registerable_actions_partial_support(self):
        """Test _get_registerable_actions with a ViewSet supporting only some actions."""
        from rest_framework.viewsets import GenericViewSet
        from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
        
        # Use GenericViewSet with specific mixins for a real partial ViewSet
        class PartialViewSet(ListModelMixin, RetrieveModelMixin, GenericViewSet):
            pass
        
        actions = self.registry._get_registerable_actions(PartialViewSet)
        # Since it only has List and Retrieve mixins, it should only have those actions
        self.assertEqual(set(actions), {'list', 'retrieve'})
    
    def test_get_all_tools(self):
        """Test getting all tools from registered ViewSets."""
        # Register a ViewSet
        self.registry.register_viewset(self.MockViewSet, base_name='test')
        
        # Get all tools
        tools = self.registry.get_all_tools()
        
        # Should have 6 tools (list, retrieve, create, update, partial_update, destroy)
        self.assertEqual(len(tools), 6)
        
        # Check tool names
        tool_names = [t.name for t in tools]
        self.assertIn('list_test', tool_names)
        self.assertIn('retrieve_test', tool_names)
        self.assertIn('create_test', tool_names)
        self.assertIn('update_test', tool_names)
        self.assertIn('partial_update_test', tool_names)
        self.assertIn('destroy_test', tool_names)
        
        # Check tool structure
        list_tool = next(t for t in tools if t.name == 'list_test')
        self.assertEqual(list_tool.viewset_class, self.MockViewSet)
        self.assertEqual(list_tool.action, 'list')
        self.assertEqual(list_tool.description, 'List test')
    
    
    def test_get_tool_by_name(self):
        """Test getting a specific tool by name."""
        self.registry.register_viewset(self.MockViewSet, base_name='test')
        
        tool = self.registry.get_tool_by_name('list_test')
        
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, 'list_test')
        self.assertEqual(tool.action, 'list')
        self.assertEqual(tool.viewset_class, self.MockViewSet)
    
    def test_get_tool_by_name_not_found(self):
        """Test getting a non-existent tool returns None."""
        tool = self.registry.get_tool_by_name('nonexistent')
        self.assertIsNone(tool)
    
    def test_clear(self):
        """Test clearing all registered tools."""
        self.registry.register_viewset(self.MockViewSet, base_name="test_tools")
        tools = self.registry.get_all_tools()
        self.assertGreater(len(tools), 0)
        
        self.registry.clear()
        tools = self.registry.get_all_tools()
        self.assertEqual(len(tools), 0)
    
    def test_tool_descriptions(self):
        """Test that tool descriptions are generated correctly."""
        self.registry.register_viewset(self.MockViewSet, base_name='customer')
        
        tools = self.registry.get_all_tools()
        
        # Check default descriptions
        list_tool = next(t for t in tools if t.action == 'list')
        self.assertEqual(list_tool.description, 'List customer')
        
        retrieve_tool = next(t for t in tools if t.action == 'retrieve')
        self.assertEqual(retrieve_tool.description, 'Retrieve customer')
        
        create_tool = next(t for t in tools if t.action == 'create')
        self.assertEqual(create_tool.description, 'Create customer')
        
        update_tool = next(t for t in tools if t.action == 'update')
        self.assertEqual(update_tool.description, 'Update customer')
        
        partial_update_tool = next(t for t in tools if t.action == 'partial_update')
        self.assertEqual(partial_update_tool.description, 'Partial_update customer')
        
        destroy_tool = next(t for t in tools if t.action == 'destroy')
        self.assertEqual(destroy_tool.description, 'Destroy customer')
    
    def test_global_registry_instance(self):
        """Test that the global registry instance exists."""
        self.assertIsInstance(registry, MCPRegistry)
    
    def test_global_registry_functionality(self):
        """Test that the global registry works correctly."""
        # Clear it first in case other tests used it
        registry.clear()
        
        registry.register_viewset(self.MockViewSet, base_name='global_test')
        
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 6)
        
        tool_names = [t.name for t in tools]
        self.assertIn('list_global_test', tool_names)


    def test_tool_titles(self):
        """Test that tool titles are generated correctly."""
        self.registry.register_viewset(self.MockViewSet, base_name='customer')
        
        tools = self.registry.get_all_tools()
        
        # Check generated titles
        list_tool = next(t for t in tools if t.action == 'list')
        self.assertEqual(list_tool.title, 'List Customer')
        
        retrieve_tool = next(t for t in tools if t.action == 'retrieve')
        self.assertEqual(retrieve_tool.title, 'Get Customer')
        
        create_tool = next(t for t in tools if t.action == 'create')
        self.assertEqual(create_tool.title, 'Create Customer')
        
        update_tool = next(t for t in tools if t.action == 'update')
        self.assertEqual(update_tool.title, 'Update Customer')
        
        partial_update_tool = next(t for t in tools if t.action == 'partial_update')
        self.assertEqual(partial_update_tool.title, 'Partially Update Customer')
        
        destroy_tool = next(t for t in tools if t.action == 'destroy')
        self.assertEqual(destroy_tool.title, 'Delete Customer')
    
    def test_tool_titles_with_plural_base(self):
        """Test title generation with plural base names."""
        self.registry.register_viewset(self.MockViewSet, base_name='customers')
        
        tools = self.registry.get_all_tools()
        
        # Check that singular forms are used appropriately
        retrieve_tool = next(t for t in tools if t.action == 'retrieve')
        self.assertEqual(retrieve_tool.title, 'Get Customer')  # Singular for individual item
        
        list_tool = next(t for t in tools if t.action == 'list')
        self.assertEqual(list_tool.title, 'List Customers')  # Plural for list

    def test_custom_action_detection(self):
        """Test that custom @action decorated methods are detected."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response
        from djangorestframework_mcp.decorators import mcp_tool
        
        class CustomActionViewSet(viewsets.ModelViewSet):
            def get_queryset(self):
                return Mock().objects.all()
            
            @mcp_tool(input_serializer=None)
            @action(detail=False, methods=['get'])
            def recent_items(self, request):
                return Response([])
            
            @mcp_tool(input_serializer=None)
            @action(detail=True, methods=['post'])
            def mark_as_favorite(self, request, pk=None):
                return Response({'favorited': True})
        
        self.registry.register_viewset(CustomActionViewSet, base_name='item')
        
        tools = self.registry.get_all_tools()
        tool_names = [t.name for t in tools]
        
        # Should include standard CRUD actions
        self.assertIn('list_item', tool_names)
        self.assertIn('retrieve_item', tool_names)
        self.assertIn('create_item', tool_names)
        self.assertIn('update_item', tool_names)
        self.assertIn('partial_update_item', tool_names)
        self.assertIn('destroy_item', tool_names)
        
        # Should include custom actions
        self.assertIn('recent_items_item', tool_names)
        self.assertIn('mark_as_favorite_item', tool_names)
        
        # Verify we have the expected number of tools (6 standard + 2 custom = 8)
        self.assertEqual(len(tools), 8)


if __name__ == '__main__':
    unittest.main()