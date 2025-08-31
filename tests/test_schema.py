"""Unit tests for schema module."""

import unittest
from unittest.mock import Mock, patch

from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet

from djangorestframework_mcp.registry import registry
from djangorestframework_mcp.schema import (
    field_to_json_schema,
    generate_body_schema,
    generate_kwargs_schema,
    generate_tool_schema,
    get_serializer_schema,
)
from djangorestframework_mcp.types import MCPTool


class TestFieldToJsonSchema(unittest.TestCase):
    """Test field_to_json_schema function."""

    def test_char_field(self):
        """Test CharField conversion."""
        field = serializers.CharField(
            max_length=100, min_length=5, help_text="A test field"
        )
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["maxLength"], 100)
        self.assertEqual(schema["minLength"], 5)
        self.assertEqual(schema["description"], "A test field")

    def test_char_field_no_constraints(self):
        """Test CharField without length constraints."""
        field = serializers.CharField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertNotIn("maxLength", schema)
        self.assertNotIn("minLength", schema)

    def test_integer_field(self):
        """Test IntegerField conversion."""
        field = serializers.IntegerField(max_value=1000, min_value=1)
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "integer")
        self.assertEqual(schema["maximum"], 1000)
        self.assertEqual(schema["minimum"], 1)

    def test_float_field(self):
        """Test FloatField conversion."""
        field = serializers.FloatField(max_value=99.9, min_value=0.1)
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "number")
        self.assertEqual(schema["maximum"], 99.9)
        self.assertEqual(schema["minimum"], 0.1)

    def test_boolean_field(self):
        """Test BooleanField conversion."""
        field = serializers.BooleanField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "boolean")

    def test_datetime_field(self):
        """Test DateTimeField conversion."""
        field = serializers.DateTimeField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "date-time")
        self.assertIn("DateTime in format: ISO-8601", schema["description"])

    def test_date_field(self):
        """Test DateField conversion."""
        field = serializers.DateField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "date")
        self.assertIn("Date in format: ISO-8601", schema["description"])

    def test_time_field(self):
        """Test TimeField conversion - adds format info to description since MCP has no time format."""
        field = serializers.TimeField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertIn("Time in format: ISO-8601", schema["description"])
        self.assertNotIn("format", schema)  # MCP doesn't have a 'time' format

    def test_uuid_field(self):
        """Test UUIDField conversion - adds format info to description since MCP has no uuid format."""
        field = serializers.UUIDField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertIn("UUID format", schema["description"])
        self.assertNotIn("format", schema)  # MCP doesn't have a 'uuid' format

    def test_email_field(self):
        """Test EmailField conversion."""
        field = serializers.EmailField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "email")

    def test_url_field(self):
        """Test URLField conversion."""
        field = serializers.URLField()
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "uri")

    def test_decimal_field(self):
        """Test DecimalField conversion - adds decimal info to description."""
        field = serializers.DecimalField(max_digits=10, decimal_places=2)
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertIn("Decimal", schema["description"])
        self.assertIn("max 10 digits", schema["description"])
        self.assertIn("2 decimal places", schema["description"])
        self.assertNotIn("format", schema)  # MCP doesn't have a 'decimal' format

    def test_unknown_field_type(self):
        """Test unknown field type raises an informative error."""
        # Create a mock field that doesn't match known types
        field = Mock(spec=serializers.Field)
        field.help_text = None
        field.label = None

        with self.assertRaises(ValueError) as context:
            field_to_json_schema(field)

        self.assertIn("Unsupported field type: Mock", str(context.exception))

    def test_field_with_label(self):
        """Test field with label as title."""
        field = serializers.CharField(label="Test Label")
        schema = field_to_json_schema(field)

        # Label should be used as title per MCP protocol
        self.assertEqual(schema["title"], "Test Label")
        # Without help_text, there should be no description
        self.assertNotIn("description", schema)

    def test_field_with_help_text_and_label(self):
        """Test field with both help_text and label."""
        field = serializers.CharField(
            label="Field Title", help_text="This is a helpful description"
        )
        schema = field_to_json_schema(field)

        # Label should be title, help_text should be description
        self.assertEqual(schema["title"], "Field Title")
        self.assertEqual(schema["description"], "This is a helpful description")

    def test_field_with_default(self):
        """Test field with default value."""
        field = serializers.CharField(default="default_value")
        schema = field_to_json_schema(field)

        self.assertEqual(schema["default"], "default_value")

    def test_field_with_callable_default(self):
        """Test field with callable default value."""

        def get_default():
            return "computed_default"

        field = serializers.CharField(default=get_default)
        schema = field_to_json_schema(field)

        self.assertEqual(schema["default"], "computed_default")

    def test_datetime_field_custom_format(self):
        """Test datetime field with custom format shows ISO-8601 in description (what DRF actually accepts)."""
        field = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "date-time")  # Always set MCP format
        self.assertEqual(schema["description"], "DateTime in format: ISO-8601")

    def test_date_field_custom_format(self):
        """Test date field with custom format shows ISO-8601 in description (what DRF actually accepts)."""
        field = serializers.DateField(format="%m/%d/%Y")
        schema = field_to_json_schema(field)

        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "date")  # Always set MCP format
        self.assertEqual(schema["description"], "Date in format: ISO-8601")

    def test_field_with_help_text_and_format_description(self):
        """Test field combines help_text with format description."""
        field = serializers.DateTimeField(
            format="%Y-%m-%d %H:%M:%S", help_text="When the event occurred"
        )
        schema = field_to_json_schema(field)

        # Should combine help_text and format description (ISO-8601 since that's what DRF accepts)
        self.assertIn("When the event occurred", schema["description"])
        self.assertIn("DateTime in format: ISO-8601", schema["description"])
        self.assertEqual(
            schema["description"],
            "When the event occurred. DateTime in format: ISO-8601",
        )


class TestSerializerToJsonSchema(unittest.TestCase):
    """Test get_serializer_schema function."""

    def setUp(self):
        """Set up test serializers."""

        class TestSerializer(serializers.Serializer):
            id = serializers.UUIDField(read_only=True)
            name = serializers.CharField(max_length=100, help_text="Full name")
            email = serializers.EmailField(help_text="Email address")
            age = serializers.IntegerField(min_value=0, required=False)
            is_active = serializers.BooleanField(default=True)
            created_at = serializers.DateTimeField(read_only=True)
            password = serializers.CharField(write_only=True, min_length=8)

        self.TestSerializer = TestSerializer

    def test_input_schema(self):
        """Test schema generation for input (write operations)."""
        schema = get_serializer_schema(self.TestSerializer())

        self.assertEqual(schema["type"], "object")

        # Should include write fields, exclude read-only
        expected_fields = {"name", "email", "age", "is_active", "password"}
        self.assertEqual(set(schema["properties"].keys()), expected_fields)

        # Check required fields (required=True and not read_only)
        # Note: is_active has default=True so it's not required
        expected_required = {"name", "email", "password"}
        self.assertEqual(set(schema["required"]), expected_required)

        # Check field types
        self.assertEqual(schema["properties"]["name"]["type"], "string")
        self.assertEqual(schema["properties"]["email"]["type"], "string")
        self.assertEqual(schema["properties"]["age"]["type"], "integer")
        self.assertEqual(schema["properties"]["is_active"]["type"], "boolean")

    def test_empty_serializer(self):
        """Test schema generation for empty serializer."""

        class EmptySerializer(serializers.Serializer):
            pass

        schema = get_serializer_schema(EmptySerializer())

        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["properties"], {})
        self.assertIn("required", schema)
        self.assertEqual(schema["required"], [])

    def test_all_optional_fields(self):
        """Test serializer with all optional fields."""

        class OptionalSerializer(serializers.Serializer):
            field1 = serializers.CharField(required=False)
            field2 = serializers.IntegerField(required=False)

        schema = get_serializer_schema(OptionalSerializer())

        self.assertEqual(len(schema["properties"]), 2)
        self.assertIn("required", schema)
        self.assertEqual(schema["required"], [])


class TestGenerateToolSchema(unittest.TestCase):
    """Test generate_tool_schema function."""

    def setUp(self):
        """Set up test fixtures."""

        # Create a mock serializer
        class MockSerializer(serializers.Serializer):
            name = serializers.CharField(max_length=100, help_text="Full name")
            email = serializers.EmailField(help_text="Email address")
            age = serializers.IntegerField(required=False, help_text="Age in years")

        # Create a mock ViewSet
        class MockViewSet(ModelViewSet):
            serializer_class = MockSerializer

            def get_serializer_class(self):
                return self.serializer_class

        self.MockViewSet = MockViewSet
        self.MockSerializer = MockSerializer

    def test_list_action_schema(self):
        """Test schema generation for list action."""
        tool = MCPTool(name="list_test", viewset_class=self.MockViewSet, action="list")
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")
        self.assertEqual(input_schema["properties"], {})
        self.assertEqual(input_schema["required"], [])

    def test_retrieve_action_schema(self):
        """Test schema generation for retrieve action."""
        tool = MCPTool(
            name="retrieve_test", viewset_class=self.MockViewSet, action="retrieve"
        )
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have kwargs with pk
        self.assertIn("kwargs", input_schema["properties"])
        kwargs_schema = input_schema["properties"]["kwargs"]
        self.assertIn("pk", kwargs_schema["properties"])
        self.assertEqual(kwargs_schema["properties"]["pk"]["type"], "string")
        self.assertEqual(kwargs_schema["required"], ["pk"])
        self.assertEqual(input_schema["required"], ["kwargs"])

    def test_create_action_schema(self):
        """Test schema generation for create action."""
        tool = MCPTool(
            name="create_test", viewset_class=self.MockViewSet, action="create"
        )
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have body with serializer fields
        self.assertIn("body", input_schema["properties"])
        body_schema = input_schema["properties"]["body"]
        expected_fields = {"name", "email", "age"}
        self.assertEqual(set(body_schema["properties"].keys()), expected_fields)

        # Check required fields in body
        expected_required = {"name", "email"}  # age is not required
        self.assertEqual(set(body_schema["required"]), expected_required)

        # Body should be required at top level
        self.assertEqual(input_schema["required"], ["body"])

    def test_update_action_schema(self):
        """Test schema generation for update action."""
        tool = MCPTool(
            name="update_test", viewset_class=self.MockViewSet, action="update"
        )
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have kwargs and body
        self.assertEqual(set(input_schema["properties"].keys()), {"kwargs", "body"})

        # Check kwargs has pk
        kwargs_schema = input_schema["properties"]["kwargs"]
        self.assertIn("pk", kwargs_schema["properties"])
        self.assertEqual(kwargs_schema["required"], ["pk"])

        # Check body has serializer fields
        body_schema = input_schema["properties"]["body"]
        expected_fields = {"name", "email", "age"}
        self.assertEqual(set(body_schema["properties"].keys()), expected_fields)
        self.assertEqual(set(body_schema["required"]), {"name", "email"})

        # Both kwargs and body should be required at top level
        self.assertEqual(set(input_schema["required"]), {"kwargs", "body"})

    def test_partial_update_action_schema(self):
        """Test schema generation for partial_update action."""
        tool = MCPTool(
            name="partial_update_test",
            viewset_class=self.MockViewSet,
            action="partial_update",
        )
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have kwargs and body
        self.assertEqual(set(input_schema["properties"].keys()), {"kwargs", "body"})

        # Check kwargs has only pk (no partial parameter)
        kwargs_schema = input_schema["properties"]["kwargs"]
        self.assertIn("pk", kwargs_schema["properties"])
        self.assertNotIn("partial", kwargs_schema["properties"])

        # Only pk should be required
        self.assertEqual(kwargs_schema["required"], ["pk"])

        # Check body has serializer fields
        body_schema = input_schema["properties"]["body"]
        expected_fields = {"name", "email", "age"}
        self.assertEqual(set(body_schema["properties"].keys()), expected_fields)

        # Both kwargs and body should be required at top level
        self.assertEqual(input_schema["required"], ["kwargs", "body"])

    def test_destroy_action_schema(self):
        """Test schema generation for destroy action."""
        tool = MCPTool(
            name="destroy_test", viewset_class=self.MockViewSet, action="destroy"
        )
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have kwargs with pk
        self.assertIn("kwargs", input_schema["properties"])
        kwargs_schema = input_schema["properties"]["kwargs"]
        self.assertIn("pk", kwargs_schema["properties"])
        self.assertEqual(kwargs_schema["properties"]["pk"]["type"], "string")
        self.assertEqual(kwargs_schema["required"], ["pk"])
        self.assertEqual(input_schema["required"], ["kwargs"])

    def test_viewset_without_serializer_class(self):
        """Test schema generation for ViewSet without serializer_class raises AssertionError."""

        class NoSerializerViewSet(ModelViewSet):
            pass

        tool = MCPTool(
            name="test_no_serializer",
            viewset_class=NoSerializerViewSet,
            action="create",
        )
        with self.assertRaises(AssertionError):
            generate_tool_schema(tool)

    def test_viewset_without_serializer_class_but_with_input_serializer(self):
        """Test that ViewSet without serializer_class works when input_serializer is provided."""

        class CustomInputSerializer(serializers.Serializer):
            custom_field = serializers.CharField(help_text="Custom input field")

        class NoSerializerViewSet(ModelViewSet):
            # No serializer_class defined
            pass

        # Create tool with explicit input_serializer
        tool = MCPTool(
            name="test_custom_input", viewset_class=NoSerializerViewSet, action="create"
        )
        tool.input_serializer = CustomInputSerializer

        # Should work without error since input_serializer is provided
        schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]
        self.assertEqual(input_schema["type"], "object")

        # Should have body with the custom serializer fields
        self.assertIn("body", input_schema["properties"])
        body_schema = input_schema["properties"]["body"]
        self.assertIn("custom_field", body_schema["properties"])
        self.assertEqual(body_schema["properties"]["custom_field"]["type"], "string")
        self.assertIn(
            "Custom input field",
            body_schema["properties"]["custom_field"]["description"],
        )

    def test_dynamic_serializer_class(self):
        """Test schema generation with dynamic serializer class method."""

        class DynamicSerializer(serializers.Serializer):
            dynamic_field = serializers.CharField()

        class DynamicViewSet(ModelViewSet):
            def get_serializer_class(self):
                return DynamicSerializer

        # Mock the instance creation and action setting
        with patch.object(DynamicViewSet, "__init__", return_value=None):
            tool = MCPTool(
                name="test_dynamic", viewset_class=DynamicViewSet, action="create"
            )
            schema = generate_tool_schema(tool)

        input_schema = schema["inputSchema"]

        # Should have body with the dynamic field
        self.assertIn("body", input_schema["properties"])
        body_schema = input_schema["properties"]["body"]
        self.assertIn("dynamic_field", body_schema["properties"])


class TestDecimalFieldIntegration(unittest.TestCase):
    """Test decimal field schema generation."""

    def test_decimal_field_precision_in_schema(self):
        """Test decimal field schema includes precision information in description."""

        class PriceSerializer(serializers.Serializer):
            price = serializers.DecimalField(max_digits=10, decimal_places=2)
            high_precision = serializers.DecimalField(max_digits=20, decimal_places=10)

        schema = get_serializer_schema(PriceSerializer())

        # Check that decimal fields have proper type and description
        price_schema = schema["properties"]["price"]
        self.assertEqual(price_schema["type"], "string")
        self.assertIn("Decimal", price_schema["description"])
        self.assertIn("max 10 digits", price_schema["description"])
        self.assertIn("2 decimal places", price_schema["description"])

        hp_schema = schema["properties"]["high_precision"]
        self.assertEqual(hp_schema["type"], "string")
        self.assertIn("Decimal", hp_schema["description"])
        self.assertIn("max 20 digits", hp_schema["description"])
        self.assertIn("10 decimal places", hp_schema["description"])


class TestCustomDateTimeFormats(unittest.TestCase):
    """Test custom datetime format handling in schema generation."""

    def test_custom_datetime_formats_in_schema(self):
        """Test that datetime fields always indicate ISO-8601 format for input (regardless of custom output formats)."""

        class EventSerializer(serializers.Serializer):
            start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
            end_time = serializers.DateTimeField(format="%m/%d/%Y %I:%M %p")
            event_date = serializers.DateField(format="%m/%d/%Y")

        schema = get_serializer_schema(EventSerializer())

        # Check that all datetime fields indicate ISO-8601 format (what DRF actually accepts for input)
        start_schema = schema["properties"]["start_time"]
        self.assertEqual(start_schema["type"], "string")
        self.assertEqual(start_schema["format"], "date-time")
        self.assertEqual(start_schema["description"], "DateTime in format: ISO-8601")

        end_schema = schema["properties"]["end_time"]
        self.assertEqual(end_schema["type"], "string")
        self.assertEqual(end_schema["format"], "date-time")
        self.assertEqual(end_schema["description"], "DateTime in format: ISO-8601")

        date_schema = schema["properties"]["event_date"]
        self.assertEqual(date_schema["type"], "string")
        self.assertEqual(date_schema["format"], "date")
        self.assertEqual(date_schema["description"], "Date in format: ISO-8601")


class TestComplexNestedStructures(unittest.TestCase):
    """Test schema generation for complex nested serializer structures."""

    def test_deeply_nested_serializers(self):
        """Test schema generation for deeply nested serializer structures."""

        class AddressSerializer(serializers.Serializer):
            street = serializers.CharField()
            city = serializers.CharField()
            state = serializers.CharField(max_length=2)
            zip_code = serializers.CharField(max_length=10)

        class ContactInfoSerializer(serializers.Serializer):
            email = serializers.EmailField()
            phone = serializers.CharField(required=False)
            address = AddressSerializer()

        class PersonSerializer(serializers.Serializer):
            name = serializers.CharField()
            contact = ContactInfoSerializer()
            emergency_contact = ContactInfoSerializer(required=False)

        schema = get_serializer_schema(PersonSerializer())

        # Check top-level structure
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertIn("contact", schema["properties"])
        self.assertIn("emergency_contact", schema["properties"])

        # Check nested contact structure
        contact_schema = schema["properties"]["contact"]
        self.assertEqual(contact_schema["type"], "object")
        self.assertIn("email", contact_schema["properties"])
        self.assertIn("phone", contact_schema["properties"])
        self.assertIn("address", contact_schema["properties"])

        # Check deeply nested address structure
        address_schema = contact_schema["properties"]["address"]
        self.assertEqual(address_schema["type"], "object")
        self.assertIn("street", address_schema["properties"])
        self.assertIn("city", address_schema["properties"])
        self.assertIn("state", address_schema["properties"])
        self.assertIn("zip_code", address_schema["properties"])

        # Check required fields at different levels
        self.assertIn("name", schema["required"])
        self.assertIn("contact", schema["required"])
        self.assertNotIn("emergency_contact", schema["required"])

        self.assertIn("email", contact_schema["required"])
        self.assertIn("address", contact_schema["required"])
        self.assertNotIn("phone", contact_schema["required"])

    def test_mixed_nested_objects_and_lists(self):
        """Test serializers that mix nested objects and lists."""

        class TagSerializer(serializers.Serializer):
            name = serializers.CharField()
            color = serializers.CharField(required=False)

        class CommentSerializer(serializers.Serializer):
            author = serializers.CharField()
            text = serializers.CharField()
            timestamp = serializers.DateTimeField()

        class PostSerializer(serializers.Serializer):
            title = serializers.CharField()
            tags = TagSerializer(many=True)
            comments = CommentSerializer(many=True, required=False)
            # Note: JSONField not yet supported, using CharField for test
            metadata = serializers.CharField(required=False, help_text="JSON metadata")

        schema = get_serializer_schema(PostSerializer())

        # Check that list fields are properly typed
        tags_schema = schema["properties"]["tags"]
        self.assertEqual(tags_schema["type"], "array")
        self.assertIn("items", tags_schema)

        # Check that list item schema is correct
        tag_item_schema = tags_schema["items"]
        self.assertEqual(tag_item_schema["type"], "object")
        self.assertIn("name", tag_item_schema["properties"])
        self.assertIn("color", tag_item_schema["properties"])
        self.assertIn("name", tag_item_schema["required"])
        self.assertNotIn("color", tag_item_schema["required"])


class TestReadOnlyFieldHandling(unittest.TestCase):
    """Test handling of read-only fields in schema generation."""

    def test_readonly_fields_excluded_from_input_schema(self):
        """Test that read-only fields are excluded from input schemas."""

        class ReadOnlySerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
            created_at = serializers.DateTimeField(read_only=True)
            updated_at = serializers.DateTimeField(read_only=True)
            name = serializers.CharField()
            value = serializers.IntegerField()
            computed_field = serializers.SerializerMethodField()

            def get_computed_field(self, obj):
                return "computed"

        schema = get_serializer_schema(ReadOnlySerializer())

        # Should include writable fields
        self.assertIn("name", schema["properties"])
        self.assertIn("value", schema["properties"])

        # Should NOT include read-only fields
        self.assertNotIn("id", schema["properties"])
        self.assertNotIn("created_at", schema["properties"])
        self.assertNotIn("updated_at", schema["properties"])
        self.assertNotIn("computed_field", schema["properties"])

        # Required fields should only include writable required fields
        self.assertIn("name", schema["required"])
        self.assertIn("value", schema["required"])
        self.assertNotIn("id", schema["required"])
        self.assertNotIn("created_at", schema["required"])

    def test_viewset_with_all_readonly_serializer(self):
        """Test ViewSet with a serializer that has only read-only fields."""

        class AllReadOnlySerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
            created_at = serializers.DateTimeField(read_only=True)
            computed = serializers.SerializerMethodField()

            def get_computed(self, obj):
                return "always_computed"

        schema = get_serializer_schema(AllReadOnlySerializer())

        # Should have empty properties and required list
        self.assertEqual(schema["properties"], {})
        self.assertEqual(schema["required"], [])
        self.assertEqual(schema["type"], "object")

    def test_recursive_serializer_handling(self):
        """Test handling of potentially recursive serializer structures."""

        class TreeNodeSerializer(serializers.Serializer):
            name = serializers.CharField()
            value = serializers.IntegerField()
            # Note: ListField not yet supported, using CharField for test
            children_ids = serializers.CharField(
                required=False, help_text="Comma-separated child IDs"
            )

        schema = get_serializer_schema(TreeNodeSerializer())

        # Should handle the string field correctly
        self.assertIn("children_ids", schema["properties"])
        children_schema = schema["properties"]["children_ids"]
        self.assertEqual(children_schema["type"], "string")
        self.assertIn("Comma-separated child IDs", children_schema["description"])

        # Should not be required
        self.assertNotIn("children_ids", schema["required"])

        # Required fields should include the required ones
        self.assertIn("name", schema["required"])
        self.assertIn("value", schema["required"])


class TestSchemaRequiredFields(unittest.TestCase):
    """Test that schema correctly determines required fields for different serializer types."""

    def test_model_serializer_required_fields(self):
        """Test all cases of required field determination for ModelSerializer."""
        from .models import RequiredFieldsTestModel

        class TestSerializer(serializers.ModelSerializer):
            class Meta:
                model = RequiredFieldsTestModel
                fields = [
                    "basic_required",
                    "with_default",
                    "with_blank",
                    "with_null",
                    "with_blank_and_null",
                    "bool_with_default",
                    "unique_with_blank_null",
                    "unique_no_blank",
                    "unique_with_default",
                    "auto_field",
                    "created_at",
                    "updated_at",
                ]

        serializer = TestSerializer()
        schema = get_serializer_schema(serializer)

        # Check which fields are marked as required
        required_fields = set(schema.get("required", []))

        # Case 1: Basic field without blank/null/default should be required
        self.assertIn("basic_required", required_fields)

        # Case 2: Field with default should NOT be required
        self.assertNotIn("with_default", required_fields)

        # Case 3: Field with blank=True should NOT be required
        self.assertNotIn("with_blank", required_fields)

        # Case 4: Field with null=True should NOT be required
        self.assertNotIn("with_null", required_fields)

        # Case 5: Field with both blank and null should NOT be required
        self.assertNotIn("with_blank_and_null", required_fields)

        # Case 6: BooleanField with default should NOT be required
        self.assertNotIn("bool_with_default", required_fields)

        # Case 7: Unique field with blank/null should NOT be required
        self.assertNotIn("unique_with_blank_null", required_fields)

        # Case 7b: Unique field without blank/null SHOULD be required
        self.assertIn("unique_no_blank", required_fields)

        # Case 8: Unique field WITH default should NOT be required
        self.assertNotIn("unique_with_default", required_fields)

        # Cases 9-11: Read-only fields should not be in properties at all
        self.assertNotIn("auto_field", schema["properties"])
        self.assertNotIn("created_at", schema["properties"])
        self.assertNotIn("updated_at", schema["properties"])

    def test_explicit_required_override(self):
        """Test that explicit required=True/False overrides model field settings."""
        from .models import RequiredFieldsTestModel

        class ExplicitSerializer(serializers.ModelSerializer):
            # Explicitly mark a normally optional field as required
            with_blank = serializers.CharField(required=True)
            # Explicitly mark a normally required field as optional
            basic_required = serializers.CharField(required=False)

            class Meta:
                model = RequiredFieldsTestModel
                fields = ["basic_required", "with_blank"]

        serializer = ExplicitSerializer()
        schema = get_serializer_schema(serializer)
        required_fields = set(schema.get("required", []))

        # with_blank should now be required due to explicit override
        self.assertIn("with_blank", required_fields)

        # basic_required should NOT be required due to explicit override
        self.assertNotIn("basic_required", required_fields)

    def test_base_serializer_required_fields(self):
        """Test required field determination for regular Serializer (not ModelSerializer)."""

        class BaseTestSerializer(serializers.Serializer):
            # Default behavior - required=True
            default_required = serializers.CharField()

            # Explicitly required
            explicit_required = serializers.CharField(required=True)

            # Explicitly optional
            explicit_optional = serializers.CharField(required=False)

            # With default value - automatically becomes optional in DRF
            # (DRF doesn't even allow default + required=True)
            with_default = serializers.CharField(default="default")

            # Boolean with default - automatically optional
            bool_with_default = serializers.BooleanField(default=True)

            # Read-only field (should not appear in schema)
            read_only_field = serializers.CharField(read_only=True)

            # allow_blank makes it accept empty strings but doesn't affect required
            allow_blank_field = serializers.CharField(allow_blank=True)

            # allow_null makes it accept None but doesn't affect required
            allow_null_field = serializers.IntegerField(allow_null=True)

        serializer = BaseTestSerializer()
        schema = get_serializer_schema(serializer)

        required_fields = set(schema.get("required", []))

        # Test default behavior - fields are required by default
        self.assertIn("default_required", required_fields)
        self.assertIn("explicit_required", required_fields)

        # Test explicitly optional fields
        self.assertNotIn("explicit_optional", required_fields)

        # In DRF, fields with defaults automatically become optional
        # You cannot have both default and required=True
        self.assertNotIn("with_default", required_fields)
        self.assertNotIn("bool_with_default", required_fields)

        # Read-only fields should not appear in schema at all
        self.assertNotIn("read_only_field", schema["properties"])

        # allow_blank and allow_null don't affect required status
        self.assertIn("allow_blank_field", required_fields)
        self.assertIn("allow_null_field", required_fields)

    def test_allow_null_fields(self):
        """Test that allow_null fields are properly represented in JSON Schema."""

        class NullTestSerializer(serializers.Serializer):
            # Standard field types without allow_null
            string_no_null = serializers.CharField()
            int_no_null = serializers.IntegerField()
            bool_no_null = serializers.BooleanField()

            # Fields with allow_null=True
            string_allow_null = serializers.CharField(allow_null=True)
            int_allow_null = serializers.IntegerField(allow_null=True)
            bool_allow_null = serializers.BooleanField(allow_null=True)

            # Combined with other options
            string_null_optional = serializers.CharField(
                allow_null=True, required=False
            )
            string_null_with_default = serializers.CharField(
                allow_null=True, default="default"
            )

            # Email and URL fields with allow_null
            email_allow_null = serializers.EmailField(allow_null=True)
            url_allow_null = serializers.URLField(allow_null=True)

        serializer = NullTestSerializer()
        schema = get_serializer_schema(serializer)

        # Test non-null fields have simple types
        self.assertEqual(schema["properties"]["string_no_null"]["type"], "string")
        self.assertEqual(schema["properties"]["int_no_null"]["type"], "integer")
        self.assertEqual(schema["properties"]["bool_no_null"]["type"], "boolean")

        # Test allow_null fields have array types with null
        self.assertEqual(
            schema["properties"]["string_allow_null"]["type"], ["string", "null"]
        )
        self.assertEqual(
            schema["properties"]["int_allow_null"]["type"], ["integer", "null"]
        )
        self.assertEqual(
            schema["properties"]["bool_allow_null"]["type"], ["boolean", "null"]
        )

        # Test combined options still work
        self.assertEqual(
            schema["properties"]["string_null_optional"]["type"], ["string", "null"]
        )
        self.assertEqual(
            schema["properties"]["string_null_with_default"]["type"], ["string", "null"]
        )

        # Test special field types with allow_null
        self.assertEqual(
            schema["properties"]["email_allow_null"]["type"], ["string", "null"]
        )
        self.assertEqual(
            schema["properties"]["url_allow_null"]["type"], ["string", "null"]
        )

        # Format should still be preserved for special fields
        self.assertEqual(schema["properties"]["email_allow_null"]["format"], "email")
        self.assertEqual(schema["properties"]["url_allow_null"]["format"], "uri")

        # Required status should be unaffected by allow_null
        required_fields = set(schema.get("required", []))
        self.assertIn("string_allow_null", required_fields)
        self.assertIn("int_allow_null", required_fields)
        self.assertIn("bool_allow_null", required_fields)
        self.assertNotIn("string_null_optional", required_fields)
        self.assertNotIn("string_null_with_default", required_fields)

    def test_model_serializer_allow_null(self):
        """Test that ModelSerializer correctly handles allow_null from model fields."""
        from .models import RequiredFieldsTestModel

        class ModelNullTestSerializer(serializers.ModelSerializer):
            class Meta:
                model = RequiredFieldsTestModel
                fields = ["with_null", "with_blank_and_null", "unique_with_blank_null"]

        serializer = ModelNullTestSerializer()
        schema = get_serializer_schema(serializer)

        # with_null (IntegerField with null=True) should allow null
        self.assertEqual(schema["properties"]["with_null"]["type"], ["integer", "null"])

        # with_blank_and_null (CharField with both) should allow null
        self.assertEqual(
            schema["properties"]["with_blank_and_null"]["type"], ["string", "null"]
        )

        # unique field with blank and null should also allow null
        self.assertEqual(
            schema["properties"]["unique_with_blank_null"]["type"], ["string", "null"]
        )


class TestListSerializerSchemaGeneration(unittest.TestCase):
    """Test schema generation for list serializers."""

    def setUp(self):
        """Set up test fixtures."""
        registry.clear()

    def test_generate_schema_from_single_serializer_class(self):
        """Test schema generation from a regular serializer class."""
        from .serializers import SimpleItemSerializer

        schema = get_serializer_schema(SimpleItemSerializer())

        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIn("name", schema["properties"])
        self.assertIn("value", schema["properties"])
        self.assertIn("is_active", schema["properties"])

        # Check field types
        self.assertEqual(schema["properties"]["name"]["type"], "string")
        self.assertEqual(schema["properties"]["value"]["type"], "integer")
        self.assertEqual(schema["properties"]["is_active"]["type"], "boolean")

    def test_generate_schema_from_list_serializer_listserializer_subclass(self):
        """Test schema generation from ListSerializer subclass."""
        from rest_framework import viewsets

        from djangorestframework_mcp.decorators import mcp_viewset
        from djangorestframework_mcp.types import MCPTool

        from .serializers import SimpleItemListSerializer

        # Create a tool with a ListSerializer to test list schema generation
        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            pass

        tool = MCPTool(name="test_tool", viewset_class=TestViewSet, action="create")
        tool.input_serializer = SimpleItemListSerializer

        body_info = generate_body_schema(tool)
        schema = body_info["schema"]

        # Should be a list schema (JSON Schema type 'array')
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)

        # Items should have the structure of SimpleItemSerializer
        item_schema = schema["items"]
        self.assertEqual(item_schema["type"], "object")
        self.assertIn("properties", item_schema)
        self.assertIn("name", item_schema["properties"])
        self.assertIn("value", item_schema["properties"])
        self.assertIn("is_active", item_schema["properties"])

    def test_generate_body_schema_with_list_input_serializer(self):
        """Test generate_body_schema with list input serializer."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import SimpleItemListSerializer

        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemListSerializer)
            @action(detail=False, methods=["post"])
            def bulk_create(self, request):
                return Response({"created": len(request.data)})

        # Get the registered tool
        tools = registry.get_all_tools()
        bulk_create_tool = next(t for t in tools if t.action == "bulk_create")

        # Generate body schema
        body_info = generate_body_schema(bulk_create_tool)

        # Should have list schema (JSON Schema type 'array')
        self.assertIsNotNone(body_info["schema"])
        self.assertEqual(body_info["schema"]["type"], "array")
        self.assertIn("items", body_info["schema"])

        # Items should be objects with our expected properties
        item_schema = body_info["schema"]["items"]
        self.assertEqual(item_schema["type"], "object")
        self.assertIn("name", item_schema["properties"])
        self.assertIn("value", item_schema["properties"])

    def test_generate_body_schema_with_single_input_serializer(self):
        """Test generate_body_schema with single input serializer (for comparison)."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        from .serializers import SimpleItemSerializer

        @mcp_viewset()
        class TestViewSet(viewsets.GenericViewSet):
            @mcp_tool(input_serializer=SimpleItemSerializer)
            @action(detail=False, methods=["post"])
            def single_create(self, request):
                return Response({"created": 1})

        # Get the registered tool
        tools = registry.get_all_tools()
        single_create_tool = next(t for t in tools if t.action == "single_create")

        # Generate body schema
        body_info = generate_body_schema(single_create_tool)

        # Should have object schema
        self.assertIsNotNone(body_info["schema"])
        self.assertEqual(body_info["schema"]["type"], "object")
        self.assertIn("properties", body_info["schema"])
        self.assertIn("name", body_info["schema"]["properties"])


class TestNestedListSerializers(unittest.TestCase):
    """Test list serializers with nested structures."""

    def setUp(self):
        """Set up test fixtures."""
        registry.clear()

    def test_nested_serializer_with_list(self):
        """Test serializer with nested lists."""
        from .serializers import ContainerSerializer

        schema = get_serializer_schema(ContainerSerializer())

        self.assertEqual(schema["type"], "object")
        self.assertIn("title", schema["properties"])
        self.assertIn("items", schema["properties"])

        # Items should be a list (JSON Schema type 'array')
        items_schema = schema["properties"]["items"]
        self.assertEqual(items_schema["type"], "array")
        self.assertIn("items", items_schema)

        # List items should be objects with id and name
        item_schema = items_schema["items"]
        self.assertEqual(item_schema["type"], "object")
        self.assertIn("id", item_schema["properties"])
        self.assertIn("name", item_schema["properties"])


class TestEnhancedLookupFieldSupport(unittest.TestCase):
    """Test enhanced lookup field support for custom fields and detail actions."""

    def setUp(self):
        """Set up test fixtures."""
        registry.clear()
        # Import decorators here to avoid circular imports
        from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

        self.mcp_viewset = mcp_viewset
        self.mcp_tool = mcp_tool

    def test_custom_lookup_field_with_slug(self):
        """Test ViewSet with custom lookup_field."""
        from rest_framework import viewsets

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class SlugCustomerViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            lookup_field = "slug"  # Use slug instead of pk

        # Get retrieve tool
        tools = registry.get_all_tools()
        retrieve_tool = next(t for t in tools if t.action == "retrieve")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(retrieve_tool)

        # Should require 'slug' parameter instead of 'pk'
        self.assertIsNotNone(kwargs_info["schema"])
        self.assertTrue(kwargs_info["is_required"])
        self.assertIn("slug", kwargs_info["schema"]["properties"])
        self.assertNotIn("pk", kwargs_info["schema"]["properties"])

        # Check description
        slug_property = kwargs_info["schema"]["properties"]["slug"]
        self.assertEqual(slug_property["type"], "string")
        self.assertEqual(slug_property["description"], "The slug of the customer")

    def test_custom_lookup_url_kwarg(self):
        """Test ViewSet with custom lookup_url_kwarg."""
        from rest_framework import viewsets

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class CustomURLKwargViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            lookup_field = "pk"
            lookup_url_kwarg = "customer_id"  # Different URL param name

        # Get retrieve tool
        tools = registry.get_all_tools()
        retrieve_tool = next(t for t in tools if t.action == "retrieve")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(retrieve_tool)

        # Should require 'customer_id' parameter
        self.assertIsNotNone(kwargs_info["schema"])
        self.assertTrue(kwargs_info["is_required"])
        self.assertIn("customer_id", kwargs_info["schema"]["properties"])
        self.assertNotIn("pk", kwargs_info["schema"]["properties"])

        # Description should show 'id' since lookup_field is 'pk' and actual field is 'id'
        customer_id_property = kwargs_info["schema"]["properties"]["customer_id"]
        self.assertEqual(customer_id_property["description"], "The id of the customer")

    def test_custom_action_with_detail_true(self):
        """Test custom action with detail=True requires lookup parameter."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class DetailActionViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer

            @self.mcp_tool(input_serializer=None)
            @action(detail=True, methods=["post"])
            def activate(self, request, pk=None):
                return Response({"activated": True})

        # Get activate tool
        tools = registry.get_all_tools()
        activate_tool = next(t for t in tools if t.action == "activate")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(activate_tool)

        # Should require pk parameter since detail=True
        self.assertIsNotNone(kwargs_info["schema"])
        self.assertTrue(kwargs_info["is_required"])
        self.assertIn("pk", kwargs_info["schema"]["properties"])
        self.assertEqual(kwargs_info["schema"]["required"], ["pk"])

        # Check that pk description shows actual primary key field name
        pk_property = kwargs_info["schema"]["properties"]["pk"]
        self.assertEqual(pk_property["description"], "The id of the customer")

    def test_custom_action_with_detail_false(self):
        """Test custom action with detail=False does not require lookup parameter."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class ListActionViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer

            @self.mcp_tool(input_serializer=None)
            @action(detail=False, methods=["get"])
            def statistics(self, request):
                return Response({"count": 10})

        # Get statistics tool
        tools = registry.get_all_tools()
        stats_tool = next(t for t in tools if t.action == "statistics")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(stats_tool)

        # Should not require any parameters since detail=False
        self.assertIsNone(kwargs_info["schema"])
        self.assertFalse(kwargs_info["is_required"])

    def test_custom_action_with_detail_true_and_custom_lookup(self):
        """Test custom action with detail=True and custom lookup field."""
        from rest_framework import viewsets
        from rest_framework.decorators import action
        from rest_framework.response import Response

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class CustomLookupDetailActionViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            lookup_field = "uuid"
            lookup_url_kwarg = "user_uuid"

            @self.mcp_tool(input_serializer=None)
            @action(detail=True, methods=["post"])
            def send_email(self, request, user_uuid=None):
                return Response({"email_sent": True})

        # Get send_email tool
        tools = registry.get_all_tools()
        email_tool = next(t for t in tools if t.action == "send_email")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(email_tool)

        # Should require user_uuid parameter
        self.assertIsNotNone(kwargs_info["schema"])
        self.assertTrue(kwargs_info["is_required"])
        self.assertIn("user_uuid", kwargs_info["schema"]["properties"])
        self.assertNotIn("pk", kwargs_info["schema"]["properties"])
        self.assertNotIn("uuid", kwargs_info["schema"]["properties"])

        # Check description for uuid field
        uuid_property = kwargs_info["schema"]["properties"]["user_uuid"]
        self.assertEqual(uuid_property["description"], "The uuid of the customer")

    def test_pk_description_fallback(self):
        """Test that 'pk' lookup field falls back to generic description when model can't be determined."""
        from rest_framework import viewsets

        from djangorestframework_mcp.types import MCPTool

        # Create a minimal viewset without proper queryset
        class MinimalViewSet(viewsets.ModelViewSet):
            def get_queryset(self):
                raise Exception("Can't get queryset")

        # Create a tool manually
        tool = MCPTool(
            name="test_tool",
            title="Test Tool",
            description="Test",
            viewset_class=MinimalViewSet,
            action="retrieve",
        )

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(tool)

        # Should fall back to 'primary key' and 'resource' when model can't be determined
        pk_property = kwargs_info["schema"]["properties"]["pk"]
        self.assertEqual(pk_property["description"], "The primary key of the resource")

    def test_pk_description_shows_actual_field_name(self):
        """Test that 'pk' lookup field shows actual primary key field name in description."""
        from rest_framework import viewsets

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class PrimaryKeyViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            # Using default lookup_field which is 'pk'

        # Get retrieve tool
        tools = registry.get_all_tools()
        retrieve_tool = next(t for t in tools if t.action == "retrieve")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(retrieve_tool)

        # Should show the actual primary key field name (id) in description
        pk_property = kwargs_info["schema"]["properties"]["pk"]
        self.assertEqual(pk_property["description"], "The id of the customer")

    def test_partial_update_only_includes_lookup_field(self):
        """Test that partial_update only includes lookup field, not partial kwarg."""
        from rest_framework import viewsets

        from .models import Customer
        from .serializers import CustomerSerializer

        @self.mcp_viewset()
        class PartialUpdateViewSet(viewsets.ModelViewSet):
            queryset = Customer.objects.all()
            serializer_class = CustomerSerializer
            lookup_field = "slug"

        # Get partial_update tool
        tools = registry.get_all_tools()
        partial_update_tool = next(t for t in tools if t.action == "partial_update")

        # Generate kwargs schema
        kwargs_info = generate_kwargs_schema(partial_update_tool)

        # Should only have slug parameter, not partial
        self.assertIsNotNone(kwargs_info["schema"])
        self.assertTrue(kwargs_info["is_required"])

        properties = kwargs_info["schema"]["properties"]
        self.assertIn("slug", properties)
        self.assertNotIn("partial", properties)

        # Only slug should be required
        self.assertEqual(kwargs_info["schema"]["required"], ["slug"])

        # Check resource name in description
        slug_property = kwargs_info["schema"]["properties"]["slug"]
        self.assertEqual(slug_property["description"], "The slug of the customer")


class TestRelationshipFieldSchemas(unittest.TestCase):
    """Test schema generation for relationship fields."""

    def test_primary_key_related_field_integer(self):
        """Test PrimaryKeyRelatedField with integer PK."""
        from .models import Customer

        field = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
        schema = field_to_json_schema(field)

        # Should be integer type for default AutoField PK
        self.assertEqual(schema["type"], "integer")

    def test_primary_key_related_field_with_allow_null(self):
        """Test PrimaryKeyRelatedField with allow_null=True."""
        from .models import Customer

        field = serializers.PrimaryKeyRelatedField(
            queryset=Customer.objects.all(), allow_null=True
        )
        schema = field_to_json_schema(field)

        # Should handle nullable
        # Could be {"type": ["integer", "null"]} or {"type": "integer", "nullable": true}
        # depending on implementation
        self.assertIn("type", schema)

    def test_primary_key_related_field_many(self):
        """Test PrimaryKeyRelatedField with many=True becomes ManyRelatedField."""
        from .models import Customer

        # When many=True, DRF wraps it in ManyRelatedField
        field = serializers.PrimaryKeyRelatedField(
            queryset=Customer.objects.all(), many=True
        )
        schema = field_to_json_schema(field)

        # Should be array of integers
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)
        self.assertEqual(schema["items"]["type"], "integer")

    def test_slug_related_field(self):
        """Test SlugRelatedField schema generation."""
        from .models import Category

        field = serializers.SlugRelatedField(
            queryset=Category.objects.all(), slug_field="slug"
        )
        schema = field_to_json_schema(field)

        # Should be string type for slug
        self.assertEqual(schema["type"], "string")
        # Could include slug_field info in description
        if "description" in schema:
            self.assertIn("slug", schema["description"].lower())

    def test_slug_related_field_with_allow_null(self):
        """Test SlugRelatedField with allow_null=True."""
        from .models import Category

        field = serializers.SlugRelatedField(
            queryset=Category.objects.all(), slug_field="slug", allow_null=True
        )
        schema = field_to_json_schema(field)

        # Should handle nullable
        self.assertIn("type", schema)

    def test_slug_related_field_many(self):
        """Test SlugRelatedField with many=True."""
        from .models import Category

        field = serializers.SlugRelatedField(
            queryset=Category.objects.all(), slug_field="slug", many=True
        )
        schema = field_to_json_schema(field)

        # Should be array of strings
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)
        self.assertEqual(schema["items"]["type"], "string")

    def test_hyperlinked_related_field(self):
        """Test HyperlinkedRelatedField schema generation."""
        from .models import Customer

        field = serializers.HyperlinkedRelatedField(
            queryset=Customer.objects.all(), view_name="customer-detail"
        )
        schema = field_to_json_schema(field)

        # Should be string with URI format
        self.assertEqual(schema["type"], "string")
        self.assertEqual(schema["format"], "uri")

    def test_hyperlinked_related_field_many(self):
        """Test HyperlinkedRelatedField with many=True."""
        from .models import Customer

        field = serializers.HyperlinkedRelatedField(
            queryset=Customer.objects.all(), view_name="customer-detail", many=True
        )
        schema = field_to_json_schema(field)

        # Should be array of URIs
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)
        self.assertEqual(schema["items"]["type"], "string")
        self.assertEqual(schema["items"]["format"], "uri")

    def test_many_related_field_wrapper(self):
        """Test that ManyRelatedField properly wraps child field schema."""
        from .models import Customer

        # Create a PrimaryKeyRelatedField with many=True
        # DRF internally creates ManyRelatedField(child=PrimaryKeyRelatedField())
        field = serializers.PrimaryKeyRelatedField(
            queryset=Customer.objects.all(), many=True
        )
        schema = field_to_json_schema(field)

        # Should wrap child schema in array
        self.assertEqual(schema["type"], "array")
        self.assertIn("items", schema)
        # Items should have the child field's schema
        self.assertEqual(schema["items"]["type"], "integer")

    def test_enhanced_field_descriptions(self):
        """Test that relationship fields generate enhanced descriptions with actual field names."""
        from .models import Category, Customer

        # Test PrimaryKeyRelatedField includes actual PK field name and "object"
        pk_field = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
        pk_schema = field_to_json_schema(pk_field)
        self.assertIn("description", pk_schema)
        description = pk_schema["description"]
        self.assertIn("id", description)  # Should mention the actual PK field name
        self.assertIn("customer", description.lower())  # Should mention the model
        self.assertIn("object", description.lower())  # Should end with "object"
        # Expected format: "Primary key (id) of customer object"
        self.assertEqual(description, "Primary key (id) of customer object")

        # Test SlugRelatedField includes actual slug field name in new format
        slug_field = serializers.SlugRelatedField(
            queryset=Category.objects.all(), slug_field="slug"
        )
        slug_schema = field_to_json_schema(slug_field)
        self.assertIn("description", slug_schema)
        slug_description = slug_schema["description"]
        self.assertIn("slug", slug_description.lower())  # Should mention slug field
        self.assertIn("category", slug_description.lower())  # Should mention model
        self.assertIn("object", slug_description.lower())  # Should include "object"
        # Expected format: "slug field of related category object"
        self.assertEqual(slug_description, "slug field of related category object")

        # Test SlugRelatedField with custom field name
        custom_slug_field = serializers.SlugRelatedField(
            queryset=Category.objects.all(), slug_field="name"
        )
        custom_schema = field_to_json_schema(custom_slug_field)
        custom_description = custom_schema["description"]
        self.assertIn("name", custom_description.lower())  # Should mention custom field
        self.assertIn("category", custom_description.lower())  # Should mention model
        # Expected format: "name field of related category object"
        self.assertEqual(custom_description, "name field of related category object")


class TestRelationshipFieldsInSerializers(unittest.TestCase):
    """Test relationship fields within serializer schemas."""

    def test_serializer_with_foreign_key(self):
        """Test serializer with ForeignKey relationship."""
        from .models import Customer

        class OrderSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
            customer = serializers.PrimaryKeyRelatedField(
                queryset=Customer.objects.all()
            )
            total = serializers.DecimalField(max_digits=10, decimal_places=2)

        schema = get_serializer_schema(OrderSerializer())

        # Should include customer field as integer
        self.assertIn("customer", schema["properties"])
        self.assertEqual(schema["properties"]["customer"]["type"], "integer")
        # Should be required
        self.assertIn("customer", schema["required"])

    def test_serializer_with_many_to_many(self):
        """Test serializer with ManyToMany relationship."""
        from .models import Product

        class TagSerializer(serializers.Serializer):
            name = serializers.CharField(max_length=50)
            products = serializers.PrimaryKeyRelatedField(
                queryset=Product.objects.all(), many=True, required=False
            )

        schema = get_serializer_schema(TagSerializer())

        # Should include products field as array
        self.assertIn("products", schema["properties"])
        products_schema = schema["properties"]["products"]
        self.assertEqual(products_schema["type"], "array")
        self.assertEqual(products_schema["items"]["type"], "integer")
        # Should not be required
        self.assertNotIn("products", schema["required"])

    def test_serializer_with_slug_relationship(self):
        """Test serializer using SlugRelatedField."""
        from .models import Category

        class ProductSerializer(serializers.Serializer):
            name = serializers.CharField(max_length=100)
            price = serializers.DecimalField(max_digits=10, decimal_places=2)
            category_slug = serializers.SlugRelatedField(
                queryset=Category.objects.all(),
                slug_field="slug",
                source="category",
                allow_null=True,
            )

        schema = get_serializer_schema(ProductSerializer())

        # Should include category_slug as string array with null (since allow_null=True)
        self.assertIn("category_slug", schema["properties"])
        self.assertEqual(
            schema["properties"]["category_slug"]["type"], ["string", "null"]
        )

    def test_serializer_with_hyperlinked_relationship(self):
        """Test serializer using HyperlinkedRelatedField."""
        from .models import Customer

        class OrderSerializer(serializers.Serializer):
            id = serializers.IntegerField(read_only=True)
            customer_url = serializers.HyperlinkedRelatedField(
                queryset=Customer.objects.all(),
                view_name="customer-detail",
                source="customer",
            )
            total = serializers.DecimalField(max_digits=10, decimal_places=2)

        schema = get_serializer_schema(OrderSerializer())

        # Should include customer_url as URI string
        self.assertIn("customer_url", schema["properties"])
        customer_schema = schema["properties"]["customer_url"]
        self.assertEqual(customer_schema["type"], "string")
        self.assertEqual(customer_schema["format"], "uri")

    def test_nested_serializer_with_relationships(self):
        """Test nested serializers containing relationship fields."""
        from .models import Category

        class CategorySerializer(serializers.Serializer):
            name = serializers.CharField()
            slug = serializers.SlugField()

        class ProductWithCategorySerializer(serializers.Serializer):
            name = serializers.CharField()
            price = serializers.DecimalField(max_digits=10, decimal_places=2)
            category = CategorySerializer()  # Nested serializer
            category_id = serializers.PrimaryKeyRelatedField(
                queryset=Category.objects.all(), source="category", write_only=True
            )

        schema = get_serializer_schema(ProductWithCategorySerializer())

        # Should include nested category object
        self.assertIn("category", schema["properties"])
        category_schema = schema["properties"]["category"]
        self.assertEqual(category_schema["type"], "object")
        self.assertIn("name", category_schema["properties"])
        self.assertIn("slug", category_schema["properties"])

        # Should include category_id for writing
        self.assertIn("category_id", schema["properties"])
        self.assertEqual(schema["properties"]["category_id"]["type"], "integer")


if __name__ == "__main__":
    unittest.main()
