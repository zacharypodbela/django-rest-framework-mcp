"""Type definitions for MCP tools."""

from dataclasses import dataclass
from typing import Optional, Type

from rest_framework.viewsets import GenericViewSet


@dataclass
class MCPTool:
    """
    Represents an MCP tool generated from a Django REST Framework ViewSet action.

    This dataclass encapsulates all the information needed to expose a ViewSet action
    as an MCP tool, including metadata and serializer configuration.
    """

    name: str
    viewset_class: Type[GenericViewSet]
    action: str
    title: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Validate the tool configuration after initialization."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not self.action:
            raise ValueError("Tool action cannot be empty")
        if not self.viewset_class:
            raise ValueError("ViewSet class is required")

    # Note: input_serializer is not a field - it's set dynamically when explicitly provided
    # This allows us to use hasattr() to check if it was set or not
