"""Registry to track MCP tools from Django REST Framework ViewSets."""

from typing import Dict, List, Optional, Type, Any
from rest_framework.viewsets import ViewSetMixin


class MCPRegistry:
    """Central registry for MCP tools."""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
    
    def register_viewset(self, viewset_class: Type[ViewSetMixin], actions: Optional[List[str]] = None, base_name: Optional[str] = None):
        """Register all actions from a ViewSet as MCP tools."""
        if base_name is None:
            # Generate base name from queryset model (if one exists) or viewset class
            # TODO: Default should be reversed to be action_base_name
            base_name = viewset_class.__name__.replace('ViewSet', '').lower()
            if hasattr(viewset_class, 'queryset') and viewset_class.queryset is not None:
                model = viewset_class.queryset.model
                base_name = model.__name__.lower() + 's'
                
        # Register each action as a separate tool
        all_actions = self._get_viewset_actions(viewset_class)
        for action_name in all_actions:
            if actions and action_name not in actions:
                continue
            
            # Check if the method has @mcp_tool metadata
            method = getattr(viewset_class, action_name, None)
            custom_name = getattr(method, '_mcp_tool_name', None) if method else None
            custom_title = getattr(method, '_mcp_title', None) if method else None
            custom_description = getattr(method, '_mcp_description', None) if method else None
            
            # Use custom values if provided, otherwise generate defaults
            tool_name = custom_name if custom_name else f"{base_name}_{action_name}"
            title = custom_title if custom_title else self._generate_tool_title(action_name, base_name)
            description = custom_description if custom_description else f"{action_name.capitalize()} {base_name}"
            
            self.register_tool(
                tool_name=tool_name,
                viewset_class=viewset_class,
                action=action_name,
                title=title,
                description=description
            )
        
        return viewset_class
    
    def register_tool(self, tool_name: str, viewset_class: Type[ViewSetMixin], action: str,
                     title: Optional[str] = None, description: Optional[str] = None):
        """Register a single action as an MCP tool."""
        tool = {
            'name': tool_name,
            'viewset_class': viewset_class,
            'action': action,
        }

        if title:
            tool['title'] = title
        if description:
            tool['description'] = description

        self._tools[tool_name] = tool
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all registered MCP tools."""
        return list(self._tools.values())
    
    def _get_viewset_actions(self, viewset_class: Type[ViewSetMixin]) -> List[str]:
        """
        Determine available actions for a ViewSet using the same approach as DRF routers.

        The logic mirrors how DRF's SimpleRouter works to create a list of endpoints when a ViewSet
        is registered without manual `.as_view` mapping. (i.e. `router.register(r'posts', PostViewSet)`)
        """
        actions = []
        
        # Standard CRUD actions
        standard_actions = ['list', 'create', 'retrieve', 'update', 'partial_update', 'destroy']
        
        # Check which standard actions the ViewSet actually implements
        # This is equivalent to router's get_method_map() logic
        for action in standard_actions:
            if hasattr(viewset_class, action):
                actions.append(action)
        
        # Use DRF's built-in method to get custom @action decorated methods
        extra_actions = viewset_class.get_extra_actions()
        for action in extra_actions:
            actions.append(action.__name__)
        
        return actions
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool by name."""
        return self._tools.get(tool_name)
    
    def _generate_tool_title(self, action: str, base_name: str) -> str:
        """Generate a human-readable title for a tool."""
        # Map actions to more readable titles
        base_title = base_name.replace('_', ' ').title()
        action_titles = {
            'list': f'List {base_title}',
            'retrieve': f'Get {base_title.rstrip("s")}',  # Remove plural 's' for single item
            'create': f'Create {base_title.rstrip("s")}',
            'update': f'Update {base_title.rstrip("s")}',
            'partial_update': f'Partially Update {base_title.rstrip("s")}',
            'destroy': f'Delete {base_title.rstrip("s")}'
        }
        return action_titles.get(action, f'{action.title()} {base_title}')
    
    def clear(self):
        """Clear all registered tools."""
        self._tools.clear()


# Global registry instance
registry = MCPRegistry()


