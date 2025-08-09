"""Decorators for exposing DRF ViewSets as MCP tools."""

from functools import wraps
from typing import Optional, Type
from rest_framework.viewsets import ViewSetMixin
from .registry import registry


class MCPToolDecorator:
    """Decorator class for marking ViewSets as MCP tools."""
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialize the MCP tool decorator.
        
        Args:
            name: Custom name for the tool set. Defaults to ViewSet's model name.
        """
        self.name = name
    
    def __call__(self, viewset_class: Type[ViewSetMixin]) -> Type[ViewSetMixin]:
        """
        Decorate a ViewSet to expose it as MCP tools.
        
        Args:
            viewset_class: The ViewSet class to decorate.
            
        Returns:
            The decorated ViewSet class.
        """
        # Register the ViewSet with the MCP registry
        registry.register(viewset_class, self.name)
        
        # Mark the class as MCP-enabled
        viewset_class._mcp_enabled = True
        viewset_class._mcp_name = self.name
        
        return viewset_class
    
    def action(self, name: Optional[str] = None, description: Optional[str] = None):
        """
        Decorator for individual ViewSet actions to customize their MCP exposure.
        
        Args:
            name: Custom name for this specific action.
            description: Description for this specific action.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                return func(self, *args, **kwargs)
            
            # Store MCP metadata on the function
            wrapper._mcp_action_name = name
            wrapper._mcp_action_description = description
            
            return wrapper
        
        return decorator


# Create the main decorator instance
mcp_tool = MCPToolDecorator