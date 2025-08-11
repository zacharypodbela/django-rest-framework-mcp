"""Decorators for exposing DRF ViewSets as MCP tools."""

from typing import Optional, Type

from rest_framework.viewsets import GenericViewSet

from .registry import registry


class MCPViewSetDecorator:
    """Decorator class for exposing GenericViewSets or individual actions as MCP tools."""

    def __init__(self, basename: Optional[str] = None, actions: Optional[list] = None):
        """
        Initialize the MCP tool decorator.

        Args:
            basename: Custom base name for the tool set. Defaults to ViewSet's model name.
            actions: List of specific actions to expose. If None, all actions are exposed.
        """
        self.basename = basename
        self.actions = actions

    def __call__(self, viewset_class: Type[GenericViewSet]) -> Type[GenericViewSet]:
        """
        Decorate a ViewSet to expose it as MCP tools.

        Args:
            viewset_class: The GenericViewSet class to decorate.

        Returns:
            The decorated ViewSet class.
        """
        # Validate that the class inherits from GenericViewSet
        if not issubclass(viewset_class, GenericViewSet):
            raise TypeError(
                f"@mcp_viewset can only be used on classes that inherit from GenericViewSet. "
                f"{viewset_class.__name__} inherits from {[cls.__name__ for cls in viewset_class.__bases__]}. "
                f"Use ModelViewSet, ReadOnlyModelViewSet, or create a custom class that inherits from GenericViewSet."
            )
        # Register the ViewSet with the MCP registry
        registry.register_viewset(viewset_class, self.actions, self.basename)

        # Mark the class as MCP-enabled
        viewset_class._mcp_enabled = True
        viewset_class._mcp_basename = self.basename

        return viewset_class


# Expose under decorator naming for use
mcp_viewset = MCPViewSetDecorator


def mcp_tool(
    name: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    input_serializer=...,
):
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

    def decorator(func):
        # Store MCP metadata directly on the function (no wrapper)
        # This is simpler and works better with @action decorator
        func._mcp_tool_name = name
        func._mcp_title = title
        func._mcp_description = description
        func._mcp_needs_registration = True

        # Validation will happen during ViewSet registration to handle both decorator orders

        # Only store serializer attributes if they were explicitly provided
        if input_serializer is not ...:
            # Validate that input_serializer is a class, not an instance
            if input_serializer is not None:
                from rest_framework import serializers

                if isinstance(input_serializer, serializers.BaseSerializer):
                    raise ValueError(
                        f"input_serializer for {func.__name__} must be a serializer class, not an instance."
                    )

            func._mcp_input_serializer = input_serializer

        return func

    return decorator
