"""Unit tests for decorators module."""

import unittest
from unittest.mock import Mock, patch
from rest_framework.viewsets import ModelViewSet, ViewSet, GenericViewSet
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views import View
from djangorestframework_mcp.decorators import MCPViewSetDecorator, mcp_viewset, mcp_tool
from djangorestframework_mcp.registry import registry
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response


class TestMCPViewSetDecorator(unittest.TestCase):
    """Test the MCPViewSetDecorator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear registry before each test
        from djangorestframework_mcp.registry import registry
        registry.clear()
    
    def test_decorator_initialization_default(self):
        """Test decorator initialization with default parameters."""
        decorator = MCPViewSetDecorator()
        self.assertIsNone(decorator.basename)
        self.assertIsNone(decorator.actions)
    
    def test_decorator_initialization_with_basename(self):
        """Test decorator initialization with custom basename."""
        decorator = MCPViewSetDecorator(basename="custom_tools")
        self.assertEqual(decorator.basename, "custom_tools")
        self.assertIsNone(decorator.actions)
    
    def test_decorator_initialization_with_actions(self):
        """Test decorator initialization with specific actions."""
        decorator = MCPViewSetDecorator(actions=['list', 'retrieve'])
        self.assertIsNone(decorator.basename)
        self.assertEqual(decorator.actions, ['list', 'retrieve'])
    
    @patch('djangorestframework_mcp.decorators.registry')
    def test_decorator_registers_all_actions(self, mock_registry):
        """Test decorator registers all ViewSet actions when no specific actions provided."""
        # Create a mock ViewSet class
        class MockViewSet(ModelViewSet):
            pass
        
        decorator = MCPViewSetDecorator(basename="test_tools")
        result = decorator(MockViewSet)
        
        # Check that registry.register_viewset was called
        mock_registry.register_viewset.assert_called_once_with(MockViewSet, None, "test_tools")
        
        # Check that the ViewSet class was modified
        self.assertEqual(result, MockViewSet)
        self.assertTrue(hasattr(result, '_mcp_enabled'))
        self.assertTrue(result._mcp_enabled)
        self.assertEqual(result._mcp_basename, "test_tools")
    
    @patch('djangorestframework_mcp.decorators.registry')
    def test_decorator_registers_specific_actions(self, mock_registry):
        """Test decorator registers only specific actions when provided."""
        class MockViewSet(ModelViewSet):
            queryset = Mock()
            queryset.model.__name__ = 'TestModel'
        
        decorator = MCPViewSetDecorator(actions=['list', 'retrieve'])
        result = decorator(MockViewSet)
        
        # Should call register_viewset with the specified actions
        self.assertEqual(mock_registry.register_viewset.call_count, 1)
        call_args = mock_registry.register_viewset.call_args
        self.assertEqual(call_args[0][0], MockViewSet)  # viewset_class
        self.assertEqual(call_args[0][1], ['list', 'retrieve'])  # actions
        self.assertEqual(call_args[0][2], None)  # base_name
    
    @patch('djangorestframework_mcp.decorators.registry')
    def test_decorator_with_default_name(self, mock_registry):
        """Test decorator with default name."""
        class MockViewSet(ModelViewSet):
            pass
        
        decorator = MCPViewSetDecorator()
        result = decorator(MockViewSet)
        
        mock_registry.register_viewset.assert_called_once_with(MockViewSet, None, None)
        self.assertIsNone(result._mcp_basename)
    
    
    def test_global_mcp_viewset_instance(self):
        """Test that the global mcp_viewset instance is properly configured."""
        self.assertEqual(mcp_viewset, MCPViewSetDecorator)
        
        # Test that it can be instantiated and called
        class MockViewSet(ModelViewSet):
            pass
        
        with patch('djangorestframework_mcp.decorators.registry') as mock_registry:
            result = mcp_viewset(basename="global_test")(MockViewSet)
            mock_registry.register_viewset.assert_called_once_with(MockViewSet, None, "global_test")
    
    def test_decorator_rejects_plain_viewset(self):
        """Test that @mcp_viewset rejects plain ViewSet (ViewSetMixin + APIView)."""
        class PlainViewSet(ViewSet):
            pass
        
        decorator = MCPViewSetDecorator()
        with self.assertRaises(TypeError) as context:
            decorator(PlainViewSet)
        
        error_msg = str(context.exception)
        self.assertIn("@mcp_viewset can only be used on classes that inherit from GenericViewSet", error_msg)
        self.assertIn("PlainViewSet", error_msg)
        self.assertIn("Use ModelViewSet, ReadOnlyModelViewSet", error_msg)
    
    def test_decorator_rejects_apiview(self):
        """Test that @mcp_viewset rejects plain APIView."""
        class MyAPIView(APIView):
            pass
        
        decorator = MCPViewSetDecorator()
        with self.assertRaises(TypeError) as context:
            decorator(MyAPIView)
        
        error_msg = str(context.exception)
        self.assertIn("@mcp_viewset can only be used on classes that inherit from GenericViewSet", error_msg)
        self.assertIn("MyAPIView", error_msg)
    
    def test_decorator_rejects_generic_apiview(self):
        """Test that @mcp_viewset rejects GenericAPIView."""
        class MyGenericView(generics.GenericAPIView):
            pass
        
        decorator = MCPViewSetDecorator()
        with self.assertRaises(TypeError) as context:
            decorator(MyGenericView)
        
        error_msg = str(context.exception)
        self.assertIn("@mcp_viewset can only be used on classes that inherit from GenericViewSet", error_msg)
        self.assertIn("MyGenericView", error_msg)
    
    def test_decorator_rejects_django_view(self):
        """Test that @mcp_viewset rejects plain Django View."""
        class MyView(View):
            pass
        
        decorator = MCPViewSetDecorator()
        with self.assertRaises(TypeError) as context:
            decorator(MyView)
        
        error_msg = str(context.exception)
        self.assertIn("@mcp_viewset can only be used on classes that inherit from GenericViewSet", error_msg)
        self.assertIn("MyView", error_msg)
    
    @patch('djangorestframework_mcp.decorators.registry')
    def test_decorator_accepts_generic_viewset(self, mock_registry):
        """Test that @mcp_viewset accepts GenericViewSet."""
        class MyGenericViewSet(GenericViewSet):
            pass
        
        decorator = MCPViewSetDecorator(basename="test_generic")
        result = decorator(MyGenericViewSet)
        
        # Should succeed without raising an error
        mock_registry.register_viewset.assert_called_once_with(MyGenericViewSet, None, "test_generic")
        self.assertEqual(result, MyGenericViewSet)


class TestMCPToolDecorator(unittest.TestCase):
    """Test the mcp_tool decorator function."""
    
    def setUp(self):
        """Set up test fixtures."""
        from djangorestframework_mcp.registry import registry
        registry.clear()
    
    def test_mcp_tool_with_default_params(self):
        """Test mcp_tool decorator with default parameters."""
        @mcp_tool()
        def create(self, request):
            return "test"
        
        # Check that the decorator adds the right metadata
        self.assertIsNone(create._mcp_tool_name)
        self.assertIsNone(create._mcp_title)
        self.assertIsNone(create._mcp_description)
        self.assertTrue(create._mcp_needs_registration)
    
    def test_mcp_tool_with_custom_params(self):
        """Test mcp_tool decorator with custom parameters."""
        @mcp_tool(
            name='custom_create_customer',
            title='Create New Customer', 
            description='Create a new customer record'
        )
        def update(self, request):
            return "test"
        
        # Check that the decorator stores the right metadata
        self.assertEqual(update._mcp_tool_name, 'custom_create_customer')
        self.assertEqual(update._mcp_title, 'Create New Customer')
        self.assertEqual(update._mcp_description, 'Create a new customer record')
        self.assertTrue(update._mcp_needs_registration)
    
    def test_mcp_tool_requires_mcp_viewset(self):
        """Test that @mcp_tool decorator only works when used with @mcp_viewset."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response
        from djangorestframework_mcp.registry import registry
        
        # ViewSet with @mcp_tool but no @mcp_viewset should not register anything
        class TestIndividualViewSet(viewsets.GenericViewSet):
            @mcp_tool(name='test_individual_action', title='Test Individual', description='Test individual tool registration')
            @action(detail=False, methods=['get'])
            def test_action(self, request):
                return Response({'test': 'data'})
        
        # Check that no tools were registered automatically
        initial_tools = registry.get_all_tools()
        test_tools = [t for t in initial_tools if t['name'] == 'test_individual_action']
        self.assertEqual(len(test_tools), 0, "@mcp_tool without @mcp_viewset should not register any tools")
        
        # Now test with @mcp_viewset - this should work
        from djangorestframework_mcp.decorators import mcp_viewset
        
        @mcp_viewset(actions=['test_action'])
        class TestRegisteredViewSet(viewsets.GenericViewSet):
            @mcp_tool(
                name='test_registered_action', 
                title='Test Registered', 
                description='Test registered tool',
                input_serializer=None
            )
            @action(detail=False, methods=['get'])
            def test_action(self, request):
                return Response({'test': 'data'})
        
        # Check that the tool was registered when using both decorators
        all_tools = registry.get_all_tools()
        registered_tools = [t for t in all_tools if t.name == 'test_registered_action']
        self.assertEqual(len(registered_tools), 1, "@mcp_tool with @mcp_viewset should register the tool")
        
        tool = registered_tools[0]
        self.assertEqual(tool.name, 'test_registered_action')
        self.assertEqual(tool.title, 'Test Registered')
        self.assertEqual(tool.description, 'Test registered tool')
    
    # Note: We no longer validate @action decorator usage at runtime
    # This is documented in README and developers should follow the documented pattern
    
    def test_mcp_tool_accepts_crud_actions_without_action_decorator(self):
        """Test that @mcp_tool works on CRUD actions without requiring @action."""
        
        # Test each CRUD action individually with proper names
        @mcp_tool(title="Test List")
        def list(self, request):
            return Response({'action': 'list'})
        
        @mcp_tool(title="Test Retrieve")
        def retrieve(self, request, pk=None):
            return Response({'action': 'retrieve'})
        
        @mcp_tool(title="Test Create")
        def create(self, request):
            return Response({'action': 'create'})
        
        @mcp_tool(title="Test Update")
        def update(self, request, pk=None):
            return Response({'action': 'update'})
        
        @mcp_tool(title="Test Partial Update")
        def partial_update(self, request, pk=None):
            return Response({'action': 'update_partial'})
        
        @mcp_tool(title="Test Destroy")
        def destroy(self, request, pk=None):
            return Response({'action': 'destroy'})
        
        # All should have MCP attributes
        for method in [list, retrieve, create, update, partial_update, destroy]:
            self.assertTrue(hasattr(method, '_mcp_needs_registration'))
            self.assertTrue(hasattr(method, '_mcp_title'))
    
    def test_mcp_tool_accepts_custom_action_with_action_decorator(self):
        """Test that @mcp_tool works correctly with custom actions that have @action decorator."""
        
        # This should work correctly (mcp_tool first)
        @mcp_tool(title="Custom Action", input_serializer=None)
        @action(detail=False, methods=['get'])
        def custom_action(self, request):
            return Response({'custom': 'action'})
        
        # Should have both MCP and action attributes
        self.assertTrue(hasattr(custom_action, '_mcp_needs_registration'))
        self.assertTrue(hasattr(custom_action, 'mapping'))
        self.assertTrue(hasattr(custom_action, 'detail'))
        self.assertEqual(custom_action.detail, False)
    
    def test_mcp_tool_accepts_both_decorator_orders(self):
        """Test that @mcp_tool works with @action in either order."""
        
        # Order 1: @mcp_tool first, @action second
        @mcp_tool(title="Order 1", input_serializer=None)
        @action(detail=False, methods=['get'])
        def custom_action_1(self, request):
            return Response({'order': 1})
        
        # Order 2: @action first, @mcp_tool second  
        @action(detail=True, methods=['post'])
        @mcp_tool(title="Order 2", input_serializer=None)
        def custom_action_2(self, request):
            return Response({'order': 2})
        
        # Both should work and have all required attributes
        for method, expected_detail in [(custom_action_1, False), (custom_action_2, True)]:
            self.assertTrue(hasattr(method, '_mcp_needs_registration'))
            self.assertTrue(hasattr(method, 'mapping'))
            self.assertTrue(hasattr(method, 'detail'))
            self.assertEqual(method.detail, expected_detail)


class TestCustomActionValidation(unittest.TestCase):
    """Test validation for custom actions requiring explicit serializers."""
    
    def setUp(self):
        """Set up test registry."""
        registry.clear()  # Clear global registry for clean test state
    
    def test_custom_action_with_explicit_serializer_success(self):
        """Test that custom actions with explicit input serializer register successfully."""
        
        class InputSerializer(serializers.Serializer):
            prompt = serializers.CharField()
        
        @mcp_viewset()
        class TestViewSet(GenericViewSet):
            @mcp_tool(input_serializer=InputSerializer)
            @action(detail=False, methods=['post'])
            def custom_action(self, request):
                return Response({'result': 'success'})
        
        # Should not raise an exception
        registry.register_viewset(TestViewSet)
        
        # Verify tool was registered
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].action, 'custom_action')
    
    def test_custom_action_with_none_serializer_success(self):
        """Test that custom actions with explicit None input serializer register successfully."""
        
        @mcp_viewset()
        class TestViewSet(GenericViewSet):
            @mcp_tool(input_serializer=None)
            @action(detail=False, methods=['get'])
            def custom_action(self, request):
                return Response({'result': 'success'})
        
        # Should not raise an exception
        registry.register_viewset(TestViewSet)
        
        # Verify tool was registered
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].action, 'custom_action')
    
    def test_custom_action_missing_input_serializer_fails(self):
        """Test that custom actions without input_serializer parameter fail validation."""
        
        with self.assertRaises(ValueError) as cm:
            @mcp_viewset()
            class TestViewSet(GenericViewSet):
                @mcp_tool()  # Missing input_serializer
                @action(detail=False, methods=['post'])
                def custom_action(self, request):
                    return Response({'result': 'success'})
        
        error_msg = str(cm.exception)
        self.assertIn("custom_action", error_msg)
        self.assertIn("input_serializer", error_msg)
        self.assertIn("@mcp_tool decorator", error_msg)
    
    def test_custom_action_missing_input_serializer_fails_without_decorator_params(self):
        """Test that custom actions with @mcp_tool() but no parameters fail validation."""
        
        with self.assertRaises(ValueError) as cm:
            @mcp_viewset()
            class TestViewSet(GenericViewSet):
                @mcp_tool()  # Missing input_serializer parameter
                @action(detail=False, methods=['post'])
                def custom_action(self, request):
                    return Response({'result': 'success'})
        
        error_msg = str(cm.exception)
        self.assertIn("custom_action", error_msg)
        self.assertIn("input_serializer", error_msg)
        self.assertIn("@mcp_tool decorator", error_msg)
    
    def test_custom_action_without_mcp_tool_decorator_not_registered(self):
        """Test that custom actions without @mcp_tool decorator are not registered as MCP tools."""
        
        @mcp_viewset()
        class TestViewSet(GenericViewSet):
            @action(detail=False, methods=['post'])
            def custom_action(self, request):
                return Response({'result': 'success'})
        
        # The ViewSet should be created without error
        # But the custom action should not be registered as a tool
        tools = registry.get_all_tools()
        tool_names = [tool.name for tool in tools]
        
        # The custom action should not be in the registered tools
        self.assertNotIn('testviewset_custom_action', tool_names)
    
    def test_crud_actions_do_not_require_explicit_serializers(self):
        """Test that CRUD actions work without explicit serializers."""
        
        class TestSerializer(serializers.Serializer):
            name = serializers.CharField()
        
        @mcp_viewset()
        class TestViewSet(GenericViewSet):
            serializer_class = TestSerializer
            
            def list(self, request):
                return Response([])
            
            def create(self, request):
                return Response({'id': 1})
        
        # Should not raise an exception
        registry.register_viewset(TestViewSet)
        
        # Verify tools were registered
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 2)
        action_names = {tool.action for tool in tools}
        self.assertEqual(action_names, {'list', 'create'})
    
    def test_crud_actions_with_explicit_input_serializer_work(self):
        """Test that CRUD actions can also have explicit input serializer."""
        
        class TestSerializer(serializers.Serializer):
            name = serializers.CharField()
        
        class CustomInputSerializer(serializers.Serializer):
            custom_field = serializers.CharField()
        
        @mcp_viewset()
        class TestViewSet(GenericViewSet):
            serializer_class = TestSerializer
            
            def list(self, request):
                return Response([])
            
            @mcp_tool(input_serializer=CustomInputSerializer)
            def create(self, request):
                return Response({'id': 1})
        
        # Should not raise an exception
        registry.register_viewset(TestViewSet)
        
        # Verify tools were registered
        tools = registry.get_all_tools()
        self.assertEqual(len(tools), 2)
        action_names = {tool.action for tool in tools}
        self.assertEqual(action_names, {'list', 'create'})


if __name__ == '__main__':
    unittest.main()