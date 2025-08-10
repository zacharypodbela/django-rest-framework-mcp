"""Decorators for exposing DRF ViewSets as MCP tools."""

from functools import wraps
from typing import Optional, Type
from rest_framework.viewsets import ViewSetMixin
from .registry import registry

class MCPViewSetDecorator:
    """Decorator class for exposing ViewSets or individual actions as MCP tools."""
    # TODO: Check to make sure this is not being decorated on something that doesn't inherit from ViewSetMixin.
    # Tests should explicitly make sure that if its called on View or GenericAPIView it throws.

    def __init__(self, name: Optional[str] = None, actions: Optional[list] = None):
        """
        Initialize the MCP tool decorator.
        
        Args:
            name: Custom base name for the tool set. Defaults to ViewSet's model name.
            actions: List of specific actions to expose. If None, all actions are exposed.
        """
        # TODO: Rename to basename to mirror the similar param that exists when defining routes in DRF
        self.name = name
        self.actions = actions
    
    def __call__(self, viewset_class: Type[ViewSetMixin]) -> Type[ViewSetMixin]:
        """
        Decorate a ViewSet to expose it as MCP tools.
        
        Args:
            viewset_class: The ViewSet class to decorate.
            
        Returns:
            The decorated ViewSet class.
        """
        # Register the ViewSet with the MCP registry
        registry.register_viewset(viewset_class, self.actions, self.name)
        
        # Mark the class as MCP-enabled
        viewset_class._mcp_enabled = True
        viewset_class._mcp_name = self.name
        
        return viewset_class

# Expose under decorator naming for use
mcp_viewset = MCPViewSetDecorator

def mcp_tool(name: Optional[str] = None, title: Optional[str] = None, 
             description: Optional[str] = None, input_serializer=...):
    """
    Decorator for individual ViewSet actions to customize their MCP tool metadata.
    
    This decorator allows customizing individual ViewSet methods when used with @mcp_viewset.
    The ViewSet class must also be decorated with @mcp_viewset for this to have any effect.
    
    Args:
        name: custom_tool_name. If not provided, will be generated from ViewSet and action.
        title: Human-readable title for the tool.
        description: Custom description for the tool.
        input_serializer: Serializer class for input validation. Required for custom actions 
                         (can be None). Optional for CRUD actions.
    
    Example:
        @mcp_viewset()
        class CustomerViewSet(ModelViewSet):
            @mcp_tool(name='list_all_customers', 
                     title='List All Customers',
                     description='Get a list of all customers in the system')
            def list(self, request):
                return super().list(request)
                
            @mcp_tool(input_serializer=GenerateInputSerializer)
            @action(detail=False, methods=['post'])
            def generate(self, request):
                return Response({'result': 'generated'})
    """
    # TODO: Do we need to check to make sure this is only being decorated on something that was decorated with @action?
    # TODO: Is there a way to make sure this is only being decorated on views that have @mcp_viewset? Or no b/c that runs after?

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        
        # Store MCP metadata on the function
        wrapper._mcp_tool_name = name
        wrapper._mcp_title = title
        wrapper._mcp_description = description
        wrapper._mcp_needs_registration = True
        
        # Only store serializer attributes if they were explicitly provided
        if input_serializer is not ...:
            # Validate that input_serializer is a class, not an instance
            if input_serializer is not None:
                from rest_framework import serializers
                if isinstance(input_serializer, serializers.BaseSerializer):
                    raise ValueError(
                        f"input_serializer for {func.__name__} must be a serializer class, not an instance."
                    )
            
            wrapper._mcp_input_serializer = input_serializer
        
        return wrapper
    
    return decorator
