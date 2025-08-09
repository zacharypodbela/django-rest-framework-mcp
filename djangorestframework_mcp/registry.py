"""Registry to track MCP-enabled ViewSets and their configurations."""

from typing import Dict, List, Optional, Type, Any
from rest_framework.viewsets import ViewSetMixin


class MCPRegistry:
    """Central registry for MCP-enabled ViewSets."""
    
    def __init__(self):
        self._viewsets: Dict[str, Dict[str, Any]] = {}
    
    def register(self, viewset_class: Type[ViewSetMixin], name: Optional[str] = None):
        """Register a ViewSet as an MCP tool."""
        if name is None:
            # Generate name from viewset class
            name = viewset_class.__name__.replace('ViewSet', '').lower()
            if hasattr(viewset_class, 'queryset') and viewset_class.queryset is not None:
                model = viewset_class.queryset.model
                name = model.__name__.lower() + 's'
        
        self._viewsets[name] = {
            'viewset_class': viewset_class,
            'name': name,
            'actions': {}
        }
        
        return viewset_class
    
    def register_action(self, viewset_name: str, action_name: str, 
                       custom_name: Optional[str] = None,
                       description: Optional[str] = None):
        """Register a specific action configuration for a ViewSet."""
        if viewset_name in self._viewsets:
            self._viewsets[viewset_name]['actions'][action_name] = {
                'name': custom_name or action_name,
                'description': description
            }
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all registered MCP tools."""
        tools = []
        for viewset_info in self._viewsets.values():
            viewset_class = viewset_info['viewset_class']
            base_name = viewset_info['name']
            
            # Get available actions from the ViewSet
            actions = self._get_viewset_actions(viewset_class)
            
            for action_name in actions:
                tool_name = f"{base_name}_{action_name}"
                action_config = viewset_info['actions'].get(action_name, {})
                
                if action_config.get('name'):
                    tool_name = action_config['name']
                
                tools.append({
                    'name': tool_name,
                    'description': action_config.get('description') or f"{action_name.capitalize()} {base_name}",
                    'viewset_class': viewset_class,
                    'action': action_name,
                    'base_name': base_name
                })
        
        return tools
    
    def _get_viewset_actions(self, viewset_class: Type[ViewSetMixin]) -> List[str]:
        """Determine available actions for a ViewSet."""
        actions = []
        
        # Standard ModelViewSet actions
        if hasattr(viewset_class, 'list'):
            actions.append('list')
        if hasattr(viewset_class, 'retrieve'):
            actions.append('retrieve')
        if hasattr(viewset_class, 'create'):
            actions.append('create')
        if hasattr(viewset_class, 'update'):
            actions.append('update')
        if hasattr(viewset_class, 'partial_update'):
            actions.append('partial_update')
        if hasattr(viewset_class, 'destroy'):
            actions.append('destroy')
        
        # TODO: Add support for custom @action decorators
        
        return actions
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool by name."""
        for tool in self.get_all_tools():
            if tool['name'] == tool_name:
                return tool
        return None
    
    def clear(self):
        """Clear all registered ViewSets."""
        self._viewsets.clear()


# Global registry instance
registry = MCPRegistry()


