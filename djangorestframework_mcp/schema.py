"""Schema generation from DRF serializers to MCP tool schemas."""

from typing import Dict, Any, Type
from rest_framework import serializers
from rest_framework.fields import Field
from rest_framework.viewsets import ViewSetMixin
from rest_framework.settings import api_settings


# Schema generator functions - each field type handles all its own logic
def get_boolean_schema(field: serializers.BooleanField) -> Dict[str, Any]:
    return {'type': 'boolean'}


def get_integer_schema(field: serializers.IntegerField) -> Dict[str, Any]:
    return {'type': 'integer'}


def get_float_schema(field: serializers.FloatField) -> Dict[str, Any]:
    return {'type': 'number'}


def get_char_schema(field: serializers.CharField) -> Dict[str, Any]:
    return {'type': 'string'}


def get_email_schema(field: serializers.EmailField) -> Dict[str, Any]:
    return {
        'type': 'string', 
        'format': 'email',
        'description': 'Valid email address (e.g., "user@example.com")'
    }


def get_url_schema(field: serializers.URLField) -> Dict[str, Any]:
    return {
        'type': 'string', 
        'format': 'uri',
        'description': 'Valid URL (e.g., "https://example.com")'
    }


def get_uuid_schema(field: serializers.UUIDField) -> Dict[str, Any]:
    return {
        'type': 'string',
        'description': 'UUID format (e.g., "123e4567-e89b-12d3-a456-426614174000")'
    }


def get_decimal_schema(field: serializers.DecimalField) -> Dict[str, Any]:
    schema = {'type': 'string'}
    
    # Add decimal precision info
    decimal_places = getattr(field, 'decimal_places', None)
    max_digits = getattr(field, 'max_digits', None)
    if decimal_places is not None or max_digits is not None:
        parts = []
        if max_digits is not None:
            parts.append(f"max {max_digits} digits")
        if decimal_places is not None:
            parts.append(f"{decimal_places} decimal places")
        schema['description'] = f"Decimal in format: ({', '.join(parts)})"
    
    return schema


def get_datetime_schema(field: serializers.DateTimeField) -> Dict[str, Any]:
    schema = {'type': 'string'}
    field_format = getattr(field, 'format', api_settings.DATETIME_FORMAT)
    schema['format'] = 'date-time'
    schema['description'] = f'DateTime in format: {field_format}'
    return schema


def get_date_schema(field: serializers.DateField) -> Dict[str, Any]:
    schema = {'type': 'string'}    
    field_format = getattr(field, 'format', api_settings.DATE_FORMAT)
    schema['format'] = 'date'
    schema['description'] = f'Date in format: {field_format}'
    return schema


def get_time_schema(field: serializers.TimeField) -> Dict[str, Any]:
    schema = {'type': 'string'}
    field_format = getattr(field, 'format', api_settings.TIME_FORMAT)
    schema['description'] = f'Time in format: {field_format}'
    return schema


# Field type registry - maps DRF field classes to their schema generator functions
FIELD_TYPE_REGISTRY = {
    serializers.BooleanField: get_boolean_schema,
    serializers.IntegerField: get_integer_schema,
    serializers.FloatField: get_float_schema,
    serializers.DecimalField: get_decimal_schema,
    serializers.CharField: get_char_schema,
    serializers.EmailField: get_email_schema,
    serializers.URLField: get_url_schema,
    serializers.UUIDField: get_uuid_schema,
    serializers.DateTimeField: get_datetime_schema,
    serializers.DateField: get_date_schema,
    serializers.TimeField: get_time_schema,
}

def get_base_schema_for_field(field: Field) -> Dict[str, Any]:
    """
    Get the complete JSON schema for a DRF field using the registry.
    
    Walks up the MRO to find the most specific registered type and calls
    its schema generator function.
    """
    # Walk up the MRO to find the most specific registered type
    for field_class in type(field).__mro__:
        if field_class in FIELD_TYPE_REGISTRY:
            schema_generator = FIELD_TYPE_REGISTRY[field_class]
            return schema_generator(field)
    
    # Default fallback for unknown types
    # TODO: Should we actually "skip" unknown types and not return them to the MCP Client at all?
    return {'type': 'string'}


def field_to_json_schema(field: Field) -> Dict[str, Any]:
    """
    Convert a DRF field to a JSON schema property definition.
    
    Maps DRF field properties to JSON Schema properties as defined in the MCP protocol:
    - type: The JSON type (string, integer, number, boolean, etc.)
    - format: Additional format hints (email, uri, date-time, etc.)
    - minimum/maximum: Value constraints for numbers
    - minLength/maxLength: Length constraints for strings
    - default: Default value if provided
    - title: Human-readable title from label
    - description: Description from help_text plus field-specific format info
    """
    # Get complete schema from registry (includes all field-specific logic)
    schema = get_base_schema_for_field(field)
    
    # Apply numeric constraints (minimum/maximum)
    if hasattr(field, 'max_value') and field.max_value is not None:
        schema['maximum'] = field.max_value
    if hasattr(field, 'min_value') and field.min_value is not None:
        schema['minimum'] = field.min_value
    
    # Apply string constraints (minLength/maxLength)
    if hasattr(field, 'max_length') and field.max_length:
        schema['maxLength'] = field.max_length
    if hasattr(field, 'min_length') and field.min_length:
        schema['minLength'] = field.min_length
    
    # Apply default value if present
    if hasattr(field, 'default') and field.default is not serializers.empty:
        # Convert callable defaults to their values
        default = field.default() if callable(field.default) else field.default
        # Only include JSON-serializable defaults
        if default is not None:
            schema['default'] = default
    
    # Apply title from label (for UI display)
    if hasattr(field, 'label') and field.label:
        schema['title'] = field.label
    
    # Add help_text to description (may already have format info from schema generators)
    if hasattr(field, 'help_text') and field.help_text:
        if 'description' in schema:
            # Combine existing description (like "UUID format") with help_text
            schema['description'] = f"{field.help_text}. {schema['description']}"
        else:
            schema['description'] = field.help_text
    
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
    instance = viewset_class()
    instance.action = action
    # get_serializer_class() will throw an AssertionError if no serializer is set. 
    # Later we may want to support ViewSets without a serializer, but for now we require one.
    serializer_class = instance.get_serializer_class()

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