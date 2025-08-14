"""Registry to track MCP tools from Django REST Framework ViewSets."""

from typing import Dict, List, Optional, Type

from rest_framework.viewsets import GenericViewSet

from .types import MCPTool

STANDARD_ACTIONS = ["list", "create", "retrieve", "update", "partial_update", "destroy"]


class MCPRegistry:
    """Central registry for MCP tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, MCPTool] = {}

    def register_viewset(
        self,
        viewset_class: Type[GenericViewSet],
        actions: Optional[List[str]] = None,
        base_name: Optional[str] = None,
    ):
        """Register actions from a ViewSet as MCPTools."""
        if base_name is None:
            # Generate base name from queryset model (if one exists) or viewset class
            base_name = viewset_class.__name__.replace("ViewSet", "").lower()
            try:
                base_name = viewset_class.queryset.model._meta.object_name.lower() + "s"  # type: ignore[union-attr]
            except (AttributeError, TypeError):
                pass

        # Check for exact same ViewSet class registration (by object identity, not just class name)
        # This prevents accidental double registration while allowing legitimate multiple ViewSets with same model
        for existing_tool in self._tools.values():
            if existing_tool.viewset_class is viewset_class:
                # Exact same ViewSet class object registered twice - this is likely an error
                from django.core.exceptions import ImproperlyConfigured

                raise ImproperlyConfigured(
                    f"ViewSet {viewset_class.__name__} is already registered. "
                    f"Each ViewSet class should only be registered once."
                )

        # Register standard CRUD actions automatically, and custom actions only if decorated with @mcp_tool
        registerable_actions = self._get_registerable_actions(viewset_class)
        for action_name in registerable_actions:
            if actions is not None and action_name not in actions:
                continue

            # Get the method (we know it exists since _get_registerable_actions found it)
            method = getattr(viewset_class, action_name)

            custom_name = getattr(method, "_mcp_tool_name", None)
            custom_title = getattr(method, "_mcp_title", None)
            custom_description = getattr(method, "_mcp_description", None)

            # Use custom values if provided, otherwise generate defaults
            tool_name = custom_name if custom_name else f"{action_name}_{base_name}"
            title = (
                custom_title
                if custom_title
                else self._generate_tool_title(action_name, base_name)
            )
            description = (
                custom_description
                if custom_description
                else f"{action_name.capitalize()} {base_name}"
            )

            # Create the MCPTool object
            tool = MCPTool(
                name=tool_name,
                viewset_class=viewset_class,
                action=action_name,
                title=title,
                description=description,
            )

            # Set input_serializer if it was explicitly provided
            if hasattr(method, "_mcp_input_serializer"):
                tool.input_serializer = method._mcp_input_serializer
            else:
                # Custom actions must have input_serializer explicitly defined
                is_custom_action = action_name not in STANDARD_ACTIONS
                if is_custom_action:
                    raise ValueError(
                        f"Custom action '{action_name}' on {viewset_class.__name__} requires "
                        f"explicit input_serializer parameter in @mcp_tool decorator. "
                        f"This can be set to None if no input is needed."
                    )

            # Check for tool name conflicts before registering
            if tool_name in self._tools:
                from django.core.exceptions import ImproperlyConfigured

                raise ImproperlyConfigured(
                    f'Tool with name "{tool_name}" is already registered. '
                    f'Please provide a unique basename for viewset "{viewset_class.__name__}" '
                    f'or a unique name for tool "{tool_name}".'
                )

            self._tools[tool_name] = tool

        return viewset_class

    def get_all_tools(self) -> List[MCPTool]:
        """Get all registered MCP tools."""
        return list(self._tools.values())

    def _get_registerable_actions(
        self, viewset_class: Type[GenericViewSet]
    ) -> List[str]:
        """
        Get actions that should be registered as MCP tools.

        Standard CRUD actions are automatically registered if they exist.
        Custom actions are only registered if they have @mcp_tool decorator.
        """
        actions = []

        # Standard actions are automatically registered if they exist
        for action in STANDARD_ACTIONS:
            if hasattr(viewset_class, action):
                actions.append(action)

        # Custom @action decorated methods are only registered if they have @mcp_tool decoration
        extra_actions = viewset_class.get_extra_actions()
        for action in extra_actions:
            if hasattr(action, "_mcp_needs_registration"):
                actions.append(action.__name__)

        return actions

    def get_tool_by_name(self, tool_name: str) -> Optional[MCPTool]:
        """Get a specific tool by name."""
        return self._tools.get(tool_name)

    def _generate_tool_title(self, action: str, base_name: str) -> str:
        """Generate a human-readable title for a tool."""
        # Map actions to more readable titles
        base_title = base_name.replace("_", " ").title()
        action_titles = {
            "list": f"List {base_title}",
            "retrieve": f"Get {base_title.rstrip('s')}",  # Remove plural 's' for single item
            "create": f"Create {base_title.rstrip('s')}",
            "update": f"Update {base_title.rstrip('s')}",
            "partial_update": f"Partially Update {base_title.rstrip('s')}",
            "destroy": f"Delete {base_title.rstrip('s')}",
        }
        return action_titles.get(action, f"{action.title()} {base_title}")

    def clear(self):
        """Clear all registered tools."""
        self._tools.clear()


# Global registry instance
registry = MCPRegistry()
