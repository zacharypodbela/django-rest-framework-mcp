"""Schema generation from DRF serializers to MCP tool schemas."""

from typing import Dict, Any, Type
from rest_framework import serializers
from rest_framework.fields import Field
from rest_framework.viewsets import ViewSetMixin


# Field type registry - maps DRF field classes to their base JSON schema definitions
FIELD_TYPE_REGISTRY: Dict[Type[Field], Dict[str, Any]] = {
    serializers.BooleanField: {'type': 'boolean'},
    serializers.IntegerField: {'type': 'integer'},
    serializers.FloatField: {'type': 'number'},
    serializers.DecimalField: {'type': 'string', 'format': 'decimal'},
    serializers.CharField: {'type': 'string'},
    serializers.EmailField: {'type': 'string', 'format': 'email'},
    serializers.URLField: {'type': 'string', 'format': 'uri'},
    serializers.UUIDField: {'type': 'string', 'format': 'uuid'},
    serializers.DateTimeField: {'type': 'string', 'format': 'date-time'},
    serializers.DateField: {'type': 'string', 'format': 'date'},
    serializers.TimeField: {'type': 'string', 'format': 'time'},
}

def get_base_schema_for_field(field: Field) -> Dict[str, Any]:
    """
    Get the base JSON schema for a DRF field using the registry.
    
    Walks up the MRO to find the most specific registered type.
    """
    # Walk up the MRO to find the most specific registered type
    for field_class in type(field).__mro__:
        if field_class in FIELD_TYPE_REGISTRY:
            # Return a copy to avoid modifying the registry
            return FIELD_TYPE_REGISTRY[field_class].copy()
    
    # Default fallback for unknown types
    # TODO: Should we actually "skip" unknown types and not return them to the MCP Client at all?
    return {'type': 'string'}


def field_to_json_schema(field: Field) -> Dict[str, Any]:
    """
    Convert a DRF field to a JSON schema property definition.
    """
    # Get base schema from registry
    schema = get_base_schema_for_field(field)
    
    # Apply constraints
    if hasattr(field, 'max_value') and field.max_value is not None:
        schema['maximum'] = field.max_value
    if hasattr(field, 'min_value') and field.min_value is not None:
        schema['minimum'] = field.min_value
    if hasattr(field, 'max_length') and field.max_length:
        schema['maxLength'] = field.max_length
    if hasattr(field, 'min_length') and field.min_length:
        schema['minLength'] = field.min_length
    
    # Apply description from help_text or label.
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
    Generate MCP tool schema for a ViewSet action using kwargs+body structure.
    
    This separates method arguments (kwargs) from request data (body) to make
    it easier to map MCP parameters to ViewSet method calls.
    
    Args:
        viewset_class: The ViewSet class.
        action: The action name (list, retrieve, create, etc.).
    
    Returns:
        MCP tool schema dict with structured input.
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
    
    # Generate structured input schema based on action
    properties = {}
    required = []
    
    # Generate kwargs schema (method arguments)
    kwargs_properties = {}
    kwargs_required = []
    
    if action in ['retrieve', 'update', 'partial_update', 'destroy']:
        # These actions need a pk in kwargs
        kwargs_properties['pk'] = {
            'type': 'string',
            'description': 'The primary key of the resource'
        }
        kwargs_required.append('pk')
    
    if action == 'partial_update':
        # partial_update also needs partial=True in kwargs
        kwargs_properties['partial'] = {
            'type': 'boolean',
            'description': 'Whether this is a partial update',
            'default': True
        }
    
    # Add kwargs to schema if needed
    if kwargs_properties:
        properties['kwargs'] = {
            'type': 'object',
            'properties': kwargs_properties,
            'required': kwargs_required if kwargs_required else []
        }
        if kwargs_required:
            required.append('kwargs')
    
    # Generate body schema (request.data)
    if action in ['create', 'update', 'partial_update'] and serializer_class:
        body_schema = serializer_to_json_schema(serializer_class, for_input=True)
        properties['body'] = body_schema
        
        # For create and update (but not partial_update), body is required if it has required fields
        if action in ['create', 'update'] and body_schema.get('required'):
            required.append('body')
    
    # Set the final schema
    schema['inputSchema']['properties'] = properties
    if required:
        schema['inputSchema']['required'] = required
    
    return schema