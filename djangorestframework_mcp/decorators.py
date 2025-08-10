"""Decorators for exposing DRF ViewSets as MCP tools."""

from functools import wraps
from typing import Optional, Type
from rest_framework.viewsets import ViewSetMixin
from .registry import registry

# TODO: Rename to be something that is more fitting for the fact that it registers all actions in ViewSet as MCP tools
class MCPToolDecorator:
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
    
    def action(self, name: Optional[str] = None, title: Optional[str] = None, 
               description: Optional[str] = None):
        """
        Decorator for individual ViewSet actions to customize their MCP exposure.
        
        Args:
            name: Custom name for this specific action's tool.
            title: Human-readable title for the tool.
            description: Description for this specific action.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                return func(self, *args, **kwargs)
            
            # Store MCP metadata on the function
            wrapper._mcp_custom_name = name
            wrapper._mcp_title = title
            wrapper._mcp_description = description
            
            # After the ViewSet is registered, update the tool if it exists
            # This will be processed when the ViewSet class is fully defined
            wrapper._mcp_needs_update = True
            
            return wrapper
        
        return decorator

# TODO: Rename to mcp_tool
def mcp_action(viewset_class: Type[ViewSetMixin], action: str, 
               name: Optional[str] = None, title: Optional[str] = None,
               description: Optional[str] = None):
    """
    Register a single ViewSet action as an MCP tool.
    
    This function allows registering individual actions without decorating the entire ViewSet.
    
    Args:
        viewset_class: The ViewSet class containing the action.
        action: The action name to register.
        name: Custom tool name. Defaults to '{base_name}_{action}'.
        title: Human-readable title for the tool.
        description: Custom description for the tool.
    
    Example:
        mcp_action(CustomerViewSet, 'list', 
                  name='list_all_customers',
                  title='List All Customers',
                  description='Get a list of all customers in the system')
    """
    # TODO: We should DRY this up, its the same as what's in registry.py
    
    # Generate default tool name if not provided
    if name is None:
        base_name = viewset_class.__name__.replace('ViewSet', '').lower()
        if hasattr(viewset_class, 'queryset') and viewset_class.queryset is not None:
            model = viewset_class.queryset.model
            base_name = model.__name__.lower() + 's'
        name = f"{base_name}_{action}"
    
    # Register the single action as a tool
    registry.register_tool(
        tool_name=name,
        viewset_class=viewset_class,
        action=action,
        title=title,
        description=description
    )

# Create the main decorator instance
mcp_tool = MCPToolDecorator