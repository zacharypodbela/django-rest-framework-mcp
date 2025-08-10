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
            base_name = viewset_class.__name__.replace('ViewSet', '').lower()
            if hasattr(viewset_class, 'queryset') and viewset_class.queryset is not None:
                model = viewset_class.queryset.model
                base_name = model.__name__.lower() + 's'
                
        # Register each action as a separate tool
        all_actions = self._get_viewset_actions(viewset_class)
        for action_name in all_actions:
            if actions and action_name not in actions:
                continue
            tool_name = f"{base_name}_{action_name}"
            self.register_tool(
                tool_name=tool_name,
                viewset_class=viewset_class,
                action=action_name,
                title=self._generate_tool_title(action_name, base_name),
                description=f"{action_name.capitalize()} {base_name}"
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

        # TODO: LLM performance will be bad if there is no descriptions (or at least titles). We should 
        # rethink if there should be a warning here or if one of these values should be required.

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
    
    def update_tool(self, tool_name: str, title: Optional[str] = None,
                    description: Optional[str] = None, custom_name: Optional[str] = None):
        """Update an existing tool's configuration."""
        if tool_name in self._tools:
            if title is not None:
                self._tools[tool_name]['title'] = title
            if description is not None:
                self._tools[tool_name]['description'] = description
            if custom_name is not None:
                # Update the tool with new name
                tool_info = self._tools.pop(tool_name)
                tool_info['name'] = custom_name
                self._tools[custom_name] = tool_info
    
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


