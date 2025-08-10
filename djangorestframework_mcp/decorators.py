"""Decorators for exposing DRF ViewSets as MCP tools."""

from functools import wraps
from typing import Optional, Type
from rest_framework.viewsets import ViewSetMixin
from .registry import registry

class MCPViewSetDecorator:
    """Decorator class for exposing ViewSets or individual actions as MCP tools."""
    
    def __init__(self, name: Optional[str] = None, actions: Optional[list] = None):
        """
        Initialize the MCP tool decorator.
        
        Args:
            name: Custom base name for the tool set. Defaults to ViewSet's model name.
            actions: List of specific actions to expose. If None, all actions are exposed.
        """
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
             description: Optional[str] = None):
    """
    Decorator for individual ViewSet actions to expose them as MCP tools.
    
    This decorator allows registering individual ViewSet methods as MCP tools
    without decorating the entire ViewSet.
    
    Args:
        name: Custom tool name. If not provided, will be generated from ViewSet and action.
        title: Human-readable title for the tool.
        description: Custom description for the tool.
    
    Example:
        class CustomerViewSet(ModelViewSet):
            @mcp_tool(name='list_all_customers', 
                     title='List All Customers',
                     description='Get a list of all customers in the system')
            def list(self, request):
                return super().list(request)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        
        # Store MCP metadata on the function
        wrapper._mcp_custom_name = name
        wrapper._mcp_title = title
        wrapper._mcp_description = description
        wrapper._mcp_needs_registration = True
        
        return wrapper
    
    return decorator
