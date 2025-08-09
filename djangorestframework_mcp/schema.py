"""Schema generation from DRF serializers to MCP tool schemas."""

from typing import Dict, Any, Type, Optional, List
from rest_framework import serializers
from rest_framework.fields import Field
from rest_framework.viewsets import ViewSetMixin
import datetime
import uuid


def field_to_json_schema(field: Field) -> Dict[str, Any]:
    """Convert a DRF field to a JSON schema property definition."""
    schema: Dict[str, Any] = {}
    
    # Map DRF field types to JSON schema types
    # Check specific field types before their parent types
    if isinstance(field, serializers.EmailField):
        schema['type'] = 'string'
        schema['format'] = 'email'
    elif isinstance(field, serializers.URLField):
        schema['type'] = 'string'
        schema['format'] = 'uri'
    elif isinstance(field, serializers.CharField):
        schema['type'] = 'string'
        if hasattr(field, 'max_length') and field.max_length:
            schema['maxLength'] = field.max_length
        if hasattr(field, 'min_length') and field.min_length:
            schema['minLength'] = field.min_length
    elif isinstance(field, serializers.IntegerField):
        schema['type'] = 'integer'
        if hasattr(field, 'max_value') and field.max_value is not None:
            schema['maximum'] = field.max_value
        if hasattr(field, 'min_value') and field.min_value is not None:
            schema['minimum'] = field.min_value
    elif isinstance(field, serializers.FloatField):
        schema['type'] = 'number'
        if hasattr(field, 'max_value') and field.max_value is not None:
            schema['maximum'] = field.max_value
        if hasattr(field, 'min_value') and field.min_value is not None:
            schema['minimum'] = field.min_value
    elif isinstance(field, serializers.BooleanField):
        schema['type'] = 'boolean'
    elif isinstance(field, serializers.DateTimeField):
        schema['type'] = 'string'
        schema['format'] = 'date-time'
    elif isinstance(field, serializers.DateField):
        schema['type'] = 'string'
        schema['format'] = 'date'
    elif isinstance(field, serializers.TimeField):
        schema['type'] = 'string'
        schema['format'] = 'time'
    elif isinstance(field, serializers.UUIDField):
        schema['type'] = 'string'
        schema['format'] = 'uuid'
    elif isinstance(field, serializers.DecimalField):
        schema['type'] = 'string'
        schema['format'] = 'decimal'
    else:
        # Default to string for unknown field types
        schema['type'] = 'string'
    
    # Add description from help_text or label
    if hasattr(field, 'help_text') and field.help_text:
        schema['description'] = field.help_text
    elif hasattr(field, 'label') and field.label:
        schema['description'] = field.label
    
    return schema


def serializer_to_json_schema(serializer_class: Type[serializers.Serializer], 
                             for_input: bool = True) -> Dict[str, Any]:
    """
    Convert a DRF serializer to a JSON schema.
    
    Args:
        serializer_class: The serializer class to convert.
        for_input: If True, generate schema for input (write operations).
                  If False, generate schema for output (read operations).
    
    Returns:
        A JSON schema dict.
    """
    serializer = serializer_class()
    properties = {}
    required = []
    
    for field_name, field in serializer.fields.items():
        # Skip read-only fields for input schemas
        if for_input and field.read_only:
            continue
        
        # Skip write-only fields for output schemas
        if not for_input and field.write_only:
            continue
        
        properties[field_name] = field_to_json_schema(field)
        
        # Mark required fields
        if for_input and field.required and not field.read_only:
            required.append(field_name)
    
    schema = {
        'type': 'object',
        'properties': properties
    }
    
    if required:
        schema['required'] = required
    
    return schema


def generate_tool_schema(viewset_class: Type[ViewSetMixin], action: str) -> Dict[str, Any]:
    """
    Generate MCP tool schema for a ViewSet action.
    
    Args:
        viewset_class: The ViewSet class.
        action: The action name (list, retrieve, create, etc.).
    
    Returns:
        MCP tool schema dict.
    """
    schema: Dict[str, Any] = {
        'inputSchema': {
            'type': 'object',
            'properties': {},
            'required': []
        }
    }
    
    # Get the serializer class
    serializer_class = None
    if hasattr(viewset_class, 'get_serializer_class'):
        # Handle dynamic serializer class
        try:
            # Create a mock instance to get serializer class
            instance = viewset_class()
            instance.action = action
            serializer_class = instance.get_serializer_class()
        except:
            # Fallback to direct attribute
            if hasattr(viewset_class, 'serializer_class'):
                serializer_class = viewset_class.serializer_class
    elif hasattr(viewset_class, 'serializer_class'):
        serializer_class = viewset_class.serializer_class
    
    # Generate input schema based on action
    if action == 'list':
        # List action might have filter parameters
        # For MVP, we'll start simple
        pass
    elif action == 'retrieve':
        # Retrieve needs an ID parameter
        schema['inputSchema']['properties']['id'] = {
            'type': 'string',
            'description': 'The ID of the resource to retrieve'
        }
        schema['inputSchema']['required'] = ['id']
    elif action == 'create':
        # Create needs the full serializer as input
        if serializer_class:
            input_schema = serializer_to_json_schema(serializer_class, for_input=True)
            schema['inputSchema'] = input_schema
    elif action == 'update' or action == 'partial_update':
        # Update needs ID plus the serializer fields
        schema['inputSchema']['properties']['id'] = {
            'type': 'string',
            'description': 'The ID of the resource to update'
        }
        schema['inputSchema']['required'] = ['id']
        
        if serializer_class:
            input_schema = serializer_to_json_schema(serializer_class, for_input=True)
            # Merge the serializer properties
            schema['inputSchema']['properties'].update(input_schema.get('properties', {}))
            
            # For partial_update, no additional fields are required
            if action == 'update':
                # For full update, add serializer required fields
                schema['inputSchema']['required'].extend(input_schema.get('required', []))
    elif action == 'destroy':
        # Destroy needs an ID parameter
        schema['inputSchema']['properties']['id'] = {
            'type': 'string',
            'description': 'The ID of the resource to delete'
        }
        schema['inputSchema']['required'] = ['id']
    
    return schema