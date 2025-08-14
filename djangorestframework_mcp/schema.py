"""Schema generation from DRF serializers to MCP tool schemas."""

from typing import Any, Dict

from rest_framework import serializers
from rest_framework.fields import Field

from .types import MCPTool


# Schema generator functions - each field type handles all its own logic
def get_boolean_schema(field: serializers.BooleanField) -> Dict[str, Any]:
    return {"type": "boolean"}


def get_integer_schema(field: serializers.IntegerField) -> Dict[str, Any]:
    return {"type": "integer"}


def get_float_schema(field: serializers.FloatField) -> Dict[str, Any]:
    return {"type": "number"}


def get_char_schema(field: serializers.CharField) -> Dict[str, Any]:
    return {"type": "string"}


def get_email_schema(field: serializers.EmailField) -> Dict[str, Any]:
    return {
        "type": "string",
        "format": "email",
        "description": 'Valid email address (e.g., "user@example.com")',
    }


def get_url_schema(field: serializers.URLField) -> Dict[str, Any]:
    return {
        "type": "string",
        "format": "uri",
        "description": 'Valid URL (e.g., "https://example.com")',
    }


def get_uuid_schema(field: serializers.UUIDField) -> Dict[str, Any]:
    return {
        "type": "string",
        "description": 'UUID format (e.g., "123e4567-e89b-12d3-a456-426614174000")',
    }


def get_decimal_schema(field: serializers.DecimalField) -> Dict[str, Any]:
    schema = {"type": "string"}

    # Add decimal precision info
    decimal_places = getattr(field, "decimal_places", None)
    max_digits = getattr(field, "max_digits", None)
    if decimal_places is not None or max_digits is not None:
        parts = []
        if max_digits is not None:
            parts.append(f"max {max_digits} digits")
        if decimal_places is not None:
            parts.append(f"{decimal_places} decimal places")
        schema["description"] = f"Decimal in format: ({', '.join(parts)})"

    return schema


def get_datetime_schema(field: serializers.DateTimeField) -> Dict[str, Any]:
    schema = {"type": "string", "format": "date-time"}
    # Note: Unless overridden using to_representation (which we don't support yet)
    # DRF still expects input as ISO-8601 format even if `format` is set to something else
    schema["description"] = "DateTime in format: ISO-8601"
    return schema


def get_date_schema(field: serializers.DateField) -> Dict[str, Any]:
    schema = {"type": "string", "format": "date"}
    # Note: Unless overridden using to_representation (which we don't support yet)
    # DRF still expects input as ISO-8601 format even if `format` is set to something else
    schema["description"] = "Date in format: ISO-8601"
    return schema


def get_time_schema(field: serializers.TimeField) -> Dict[str, Any]:
    schema = {"type": "string"}
    # Note: Unless overridden using to_representation (which we don't support yet)
    # DRF still expects input as ISO-8601 format even if `format` is set to something else
    schema["description"] = "Time in format: ISO-8601"
    return schema


def get_serializer_schema(serializer: serializers.BaseSerializer) -> Dict[str, Any]:
    properties = {}
    required = []

    for field_name, field in serializer.fields.items():
        # Skip read-only fields for input schemas
        if field.read_only:
            continue

        properties[field_name] = field_to_json_schema(field)

        # Mark required fields
        if field.required and not field.read_only:
            required.append(field_name)

    schema = {
        "type": "object",
        "properties": properties,
        "required": required if required else [],
    }

    return schema


def get_list_serializer_schema(
    serializer: serializers.ListSerializer,
) -> Dict[str, Any]:
    if serializer.child is None:
        raise ValueError("ListSerializer must have a child serializer defined")
    child_schema = field_to_json_schema(serializer.child)
    return {"type": "array", "items": child_schema}


# Field type registry - maps DRF field classes to their schema generator functions
# These are checked in order. If a class inherits from another in the list, its important the subclass be first or it will
# never be choosen. (Ex: ListSerializer inherits from BaseSerializer)
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
    serializers.ListSerializer: get_list_serializer_schema,
    serializers.BaseSerializer: get_serializer_schema,
}


def get_base_schema_for_field(field: Field) -> Dict[str, Any]:
    """
    Get the complete JSON schema for a DRF field using the registry.

    Walks up the MRO to find the most specific registered type and calls
    its schema generator function.

    Args:
        field: The DRF field to generate schema for.

    Returns:
        Base JSON schema dict from the registry.
    """
    # Walk up the MRO to find the most specific registered type
    for field_class in type(field).__mro__:
        if field_class in FIELD_TYPE_REGISTRY:
            schema_generator = FIELD_TYPE_REGISTRY[field_class]
            # NOTE: mypy can't verify that 'field' (typed as Field) is compatible with the specific
            # function signature (e.g., BooleanField), but we know it's safe due to the MRO lookup
            # ensuring field is an instance of (or inherits from) the expected field type
            return schema_generator(field)  # type: ignore[operator]

    # Raise an error for unknown field types instead of silently defaulting to string
    field_type_name = type(field).__name__
    raise ValueError(f"Unsupported field type: {field_type_name}")


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

    Args:
        field: The DRF field to convert.

    Returns:
        A JSON schema dict representing the field.
    """
    # Get complete schema from registry (includes all field-specific logic)
    schema = get_base_schema_for_field(field)

    # Apply numeric constraints (minimum/maximum)
    if hasattr(field, "max_value") and field.max_value is not None:
        schema["maximum"] = field.max_value
    if hasattr(field, "min_value") and field.min_value is not None:
        schema["minimum"] = field.min_value

    # Apply string constraints (minLength/maxLength)
    if hasattr(field, "max_length") and field.max_length:
        schema["maxLength"] = field.max_length
    if hasattr(field, "min_length") and field.min_length:
        schema["minLength"] = field.min_length

    # Apply default value if present
    if hasattr(field, "default") and field.default is not serializers.empty:
        # Convert callable defaults to their values
        default = field.default() if callable(field.default) else field.default
        # Only include JSON-serializable defaults
        if default is not None:
            schema["default"] = default

    # Apply title from label (for UI display)
    if hasattr(field, "label") and field.label:
        schema["title"] = field.label

    # Add help_text to description (may already have format info from schema generators)
    if hasattr(field, "help_text") and field.help_text:
        if "description" in schema:
            # Combine existing description (like "UUID format") with help_text
            schema["description"] = f"{field.help_text}. {schema['description']}"
        else:
            schema["description"] = field.help_text

    return schema


def generate_body_schema(tool: MCPTool) -> Dict[str, Any]:
    """
    Generate the body schema for a ViewSet action.

    Args:
        tool: The MCPTool object containing all tool information.

    Returns:
        Dict containing body schema and whether body is required.
    """
    # Determine the serializer class to use
    serializer_class = None
    # If input serializer was explicitly provided, use it
    if hasattr(tool, "input_serializer"):
        serializer_class = tool.input_serializer

        if serializer_class is None:
            # Explicitly set to None - no input needed
            return {"schema": None, "is_required": False}

    # Fall back to using view_class serializer if input_serializer not provided
    else:
        # For list, retrieve, destroy actions where no custom input_serializer was provided, we don't expect input
        if tool.action in ["list", "retrieve", "destroy"]:
            return {"schema": None, "is_required": False}

        instance = tool.viewset_class()
        instance.action = tool.action
        serializer_class = instance.get_serializer_class()

    body_schema = field_to_json_schema(serializer_class())

    return {"schema": body_schema, "is_required": bool(body_schema.get("required"))}


def generate_kwargs_schema(tool: MCPTool) -> Dict[str, Any]:
    """
    Generate the kwargs schema for a ViewSet action.

    Args:
        tool: The MCPTool object containing all tool information.

    Returns:
        Dict containing kwargs schema and whether kwargs are required.
    """
    kwargs_properties = {}
    kwargs_required = []

    action = tool.action
    viewset_class = tool.viewset_class

    # Check if this action needs object lookup (detail=True for custom actions or standard detail actions)
    needs_lookup = False
    # Standard CRUD actions that need lookup
    if action in ["retrieve", "update", "partial_update", "destroy"]:
        needs_lookup = True
    # Check if this is a custom action with detail=True
    elif hasattr(viewset_class, action):
        method = getattr(viewset_class, action)
        if hasattr(method, "detail"):
            needs_lookup = method.detail

    if needs_lookup:
        # Get lookup_field (defaults to 'pk' in GenericAPIView)
        lookup_field = viewset_class.lookup_field

        # Get lookup_url_kwarg (defaults to lookup_field if not explicitly set)
        lookup_url_kwarg = viewset_class.lookup_url_kwarg or lookup_field

        # If the lookup_field is "pk", fetch the actual field name to share with the LLM in the description
        lookup_field_name = lookup_field
        if lookup_field == "pk":
            # Try to get the actual primary key field name from the model
            try:
                lookup_field_name = viewset_class.queryset.model._meta.pk.name  # type: ignore[union-attr]
            except Exception:
                # Fallback if we can't determine the pk field from the model
                # NOTE: This is really not ideal though. In the future we might consider stronger enforcement of requirements
                # (like requiring get_queryset be implemented) if we find that this degrades LLM ability to use detail tools
                # to the point that the tools are not really usable
                lookup_field_name = "primary key"
        # Attempt to fetch the name of the resource (if possible) to further improve description
        resource_name = "resource"
        try:
            resource_name = viewset_class.queryset.model._meta.object_name.lower()  # type: ignore[union-attr]
        except Exception:
            pass

        # Add the lookup parameter
        kwargs_properties[lookup_url_kwarg] = {
            "type": "string",
            "description": f"The {lookup_field_name} of the {resource_name}",
        }
        kwargs_required.append(lookup_url_kwarg)

    # Build the kwargs schema if we have any properties.
    if kwargs_properties:
        return {
            "schema": {
                "type": "object",
                "properties": kwargs_properties,
                "required": kwargs_required if kwargs_required else [],
            },
            "is_required": bool(kwargs_required),
        }

    return {"schema": None, "is_required": False}


def generate_tool_schema(tool: MCPTool) -> Dict[str, Any]:
    """
    Generate MCP tool schema for a ViewSet action using kwargs+body structure.

    This separates method arguments (kwargs) from request data (body) to make
    it easier to map MCP parameters to ViewSet method calls.

    Args:
        tool: The MCPTool object containing all tool information.

    Returns:
        MCP tool schema dict with structured input.
    """
    # Generate the component schemas
    kwargs_info = generate_kwargs_schema(tool)
    body_info = generate_body_schema(tool)

    # Stitch together the top-level inputSchema
    properties = {}
    required = []

    # Add kwargs if present
    if kwargs_info["schema"]:
        properties["kwargs"] = kwargs_info["schema"]
        if kwargs_info["is_required"]:
            required.append("kwargs")

    # Add body if present
    if body_info["schema"]:
        properties["body"] = body_info["schema"]
        if body_info["is_required"]:
            required.append("body")

    # Build final schema
    schema = {
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required if required else [],
        }
    }

    return schema
