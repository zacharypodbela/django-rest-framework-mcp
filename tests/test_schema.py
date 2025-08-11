"""Unit tests for schema module."""

import unittest
from unittest.mock import Mock, patch
from rest_framework import serializers
from rest_framework.viewsets import ModelViewSet
from djangorestframework_mcp.schema import (
    field_to_json_schema,
    get_serializer_schema,
    generate_tool_schema
)
from djangorestframework_mcp.types import MCPTool


class TestFieldToJsonSchema(unittest.TestCase):
    """Test field_to_json_schema function."""
    
    def test_char_field(self):
        """Test CharField conversion."""
        field = serializers.CharField(max_length=100, min_length=5, help_text="A test field")
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['maxLength'], 100)
        self.assertEqual(schema['minLength'], 5)
        self.assertEqual(schema['description'], 'A test field')
    
    def test_char_field_no_constraints(self):
        """Test CharField without length constraints."""
        field = serializers.CharField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertNotIn('maxLength', schema)
        self.assertNotIn('minLength', schema)
    
    def test_integer_field(self):
        """Test IntegerField conversion."""
        field = serializers.IntegerField(max_value=1000, min_value=1)
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'integer')
        self.assertEqual(schema['maximum'], 1000)
        self.assertEqual(schema['minimum'], 1)
    
    def test_float_field(self):
        """Test FloatField conversion."""
        field = serializers.FloatField(max_value=99.9, min_value=0.1)
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'number')
        self.assertEqual(schema['maximum'], 99.9)
        self.assertEqual(schema['minimum'], 0.1)
    
    def test_boolean_field(self):
        """Test BooleanField conversion."""
        field = serializers.BooleanField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'boolean')
    
    def test_datetime_field(self):
        """Test DateTimeField conversion."""
        field = serializers.DateTimeField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'date-time')
        self.assertIn('DateTime in format: iso-8601', schema['description'])
    
    def test_date_field(self):
        """Test DateField conversion."""
        field = serializers.DateField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'date')
        self.assertIn('Date in format: iso-8601', schema['description'])
    
    def test_time_field(self):
        """Test TimeField conversion - adds format info to description since MCP has no time format."""
        field = serializers.TimeField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertIn('Time in format: iso-8601', schema['description'])
        self.assertNotIn('format', schema)  # MCP doesn't have a 'time' format
    
    def test_uuid_field(self):
        """Test UUIDField conversion - adds format info to description since MCP has no uuid format."""
        field = serializers.UUIDField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertIn('UUID format', schema['description'])
        self.assertNotIn('format', schema)  # MCP doesn't have a 'uuid' format
    
    def test_email_field(self):
        """Test EmailField conversion."""
        field = serializers.EmailField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'email')
    
    def test_url_field(self):
        """Test URLField conversion."""
        field = serializers.URLField()
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'uri')
    
    def test_decimal_field(self):
        """Test DecimalField conversion - adds decimal info to description."""
        field = serializers.DecimalField(max_digits=10, decimal_places=2)
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertIn('Decimal', schema['description'])
        self.assertIn('max 10 digits', schema['description'])
        self.assertIn('2 decimal places', schema['description'])
        self.assertNotIn('format', schema)  # MCP doesn't have a 'decimal' format
    
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
        self.assertEqual(schema['title'], 'Test Label')
        # Without help_text, there should be no description
        self.assertNotIn('description', schema)
    
    def test_field_with_help_text_and_label(self):
        """Test field with both help_text and label."""
        field = serializers.CharField(
            label="Field Title",
            help_text="This is a helpful description"
        )
        schema = field_to_json_schema(field)
        
        # Label should be title, help_text should be description
        self.assertEqual(schema['title'], 'Field Title')
        self.assertEqual(schema['description'], 'This is a helpful description')
    
    def test_field_with_default(self):
        """Test field with default value."""
        field = serializers.CharField(default="default_value")
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['default'], 'default_value')
    
    def test_field_with_callable_default(self):
        """Test field with callable default value."""
        def get_default():
            return "computed_default"
        
        field = serializers.CharField(default=get_default)
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['default'], 'computed_default')
    
    def test_datetime_field_custom_format(self):
        """Test datetime field with custom format adds to description."""
        field = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'date-time')  # Always set MCP format
        self.assertIn('DateTime in format: %Y-%m-%d %H:%M:%S', schema['description'])
    
    def test_date_field_custom_format(self):
        """Test date field with custom format adds to description."""
        field = serializers.DateField(format='%m/%d/%Y')
        schema = field_to_json_schema(field)
        
        self.assertEqual(schema['type'], 'string')
        self.assertEqual(schema['format'], 'date')  # Always set MCP format
        self.assertIn('Date in format: %m/%d/%Y', schema['description'])
    
    def test_field_with_help_text_and_format_description(self):
        """Test field combines help_text with format description."""
        field = serializers.DateTimeField(
            format='%Y-%m-%d %H:%M:%S',
            help_text='When the event occurred'
        )
        schema = field_to_json_schema(field)
        
        # Should combine help_text and format description
        self.assertIn('When the event occurred', schema['description'])
        self.assertIn('DateTime in format: %Y-%m-%d %H:%M:%S', schema['description'])


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
        
        self.assertEqual(schema['type'], 'object')
        
        # Should include write fields, exclude read-only
        expected_fields = {'name', 'email', 'age', 'is_active', 'password'}
        self.assertEqual(set(schema['properties'].keys()), expected_fields)
        
        # Check required fields (required=True and not read_only)
        # Note: is_active has default=True so it's not required
        expected_required = {'name', 'email', 'password'}
        self.assertEqual(set(schema['required']), expected_required)
        
        # Check field types
        self.assertEqual(schema['properties']['name']['type'], 'string')
        self.assertEqual(schema['properties']['email']['type'], 'string')
        self.assertEqual(schema['properties']['age']['type'], 'integer')
        self.assertEqual(schema['properties']['is_active']['type'], 'boolean')
    
    
    def test_empty_serializer(self):
        """Test schema generation for empty serializer."""
        class EmptySerializer(serializers.Serializer):
            pass
        
        schema = get_serializer_schema(EmptySerializer())
        
        self.assertEqual(schema['type'], 'object')
        self.assertEqual(schema['properties'], {})
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], [])
    
    def test_all_optional_fields(self):
        """Test serializer with all optional fields."""
        class OptionalSerializer(serializers.Serializer):
            field1 = serializers.CharField(required=False)
            field2 = serializers.IntegerField(required=False)
        
        schema = get_serializer_schema(OptionalSerializer())
        
        self.assertEqual(len(schema['properties']), 2)
        self.assertIn('required', schema)
        self.assertEqual(schema['required'], [])


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
        tool = MCPTool(name='list_test', viewset_class=self.MockViewSet, action='list')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        self.assertEqual(input_schema['properties'], {})
        self.assertEqual(input_schema['required'], [])
    
    def test_retrieve_action_schema(self):
        """Test schema generation for retrieve action."""
        tool = MCPTool(name='retrieve_test', viewset_class=self.MockViewSet, action='retrieve')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        
        # Should have kwargs with pk
        self.assertIn('kwargs', input_schema['properties'])
        kwargs_schema = input_schema['properties']['kwargs']
        self.assertIn('pk', kwargs_schema['properties'])
        self.assertEqual(kwargs_schema['properties']['pk']['type'], 'string')
        self.assertEqual(kwargs_schema['required'], ['pk'])
        self.assertEqual(input_schema['required'], ['kwargs'])
    
    def test_create_action_schema(self):
        """Test schema generation for create action."""
        tool = MCPTool(name='create_test', viewset_class=self.MockViewSet, action='create')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        
        # Should have body with serializer fields
        self.assertIn('body', input_schema['properties'])
        body_schema = input_schema['properties']['body']
        expected_fields = {'name', 'email', 'age'}
        self.assertEqual(set(body_schema['properties'].keys()), expected_fields)
        
        # Check required fields in body
        expected_required = {'name', 'email'}  # age is not required
        self.assertEqual(set(body_schema['required']), expected_required)
        
        # Body should be required at top level
        self.assertEqual(input_schema['required'], ['body'])
    
    def test_update_action_schema(self):
        """Test schema generation for update action."""
        tool = MCPTool(name='update_test', viewset_class=self.MockViewSet, action='update')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        
        # Should have kwargs and body
        self.assertEqual(set(input_schema['properties'].keys()), {'kwargs', 'body'})
        
        # Check kwargs has pk
        kwargs_schema = input_schema['properties']['kwargs']
        self.assertIn('pk', kwargs_schema['properties'])
        self.assertEqual(kwargs_schema['required'], ['pk'])
        
        # Check body has serializer fields
        body_schema = input_schema['properties']['body']
        expected_fields = {'name', 'email', 'age'}
        self.assertEqual(set(body_schema['properties'].keys()), expected_fields)
        self.assertEqual(set(body_schema['required']), {'name', 'email'})
        
        # Both kwargs and body should be required at top level
        self.assertEqual(set(input_schema['required']), {'kwargs', 'body'})
    
    def test_partial_update_action_schema(self):
        """Test schema generation for partial_update action."""
        tool = MCPTool(name='partial_update_test', viewset_class=self.MockViewSet, action='partial_update')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        
        # Should have kwargs and body
        self.assertEqual(set(input_schema['properties'].keys()), {'kwargs', 'body'})
        
        # Check kwargs has pk and partial
        kwargs_schema = input_schema['properties']['kwargs']
        self.assertIn('pk', kwargs_schema['properties'])
        self.assertIn('partial', kwargs_schema['properties'])
        self.assertEqual(kwargs_schema['properties']['partial']['default'], True)
        self.assertEqual(kwargs_schema['required'], ['pk'])
        
        # Check body has serializer fields
        body_schema = input_schema['properties']['body']
        expected_fields = {'name', 'email', 'age'}
        self.assertEqual(set(body_schema['properties'].keys()), expected_fields)
        
        # Both kwargs and body should be required at top level
        self.assertEqual(input_schema['required'], ['kwargs', 'body'])
    
    def test_destroy_action_schema(self):
        """Test schema generation for destroy action."""
        tool = MCPTool(name='destroy_test', viewset_class=self.MockViewSet, action='destroy')
        schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        self.assertEqual(input_schema['type'], 'object')
        
        # Should have kwargs with pk
        self.assertIn('kwargs', input_schema['properties'])
        kwargs_schema = input_schema['properties']['kwargs']
        self.assertIn('pk', kwargs_schema['properties'])
        self.assertEqual(kwargs_schema['properties']['pk']['type'], 'string')
        self.assertEqual(kwargs_schema['required'], ['pk'])
        self.assertEqual(input_schema['required'], ['kwargs'])
    
    def test_viewset_without_serializer_class(self):
        """Test schema generation for ViewSet without serializer_class raises AssertionError."""
        class NoSerializerViewSet(ModelViewSet):
            pass
        
        tool = MCPTool(name='test_no_serializer', viewset_class=NoSerializerViewSet, action='create')
        with self.assertRaises(AssertionError):
            generate_tool_schema(tool)
    
    def test_dynamic_serializer_class(self):
        """Test schema generation with dynamic serializer class method."""
        class DynamicSerializer(serializers.Serializer):
            dynamic_field = serializers.CharField()
        
        class DynamicViewSet(ModelViewSet):
            def get_serializer_class(self):
                return DynamicSerializer
        
        # Mock the instance creation and action setting
        with patch.object(DynamicViewSet, '__init__', return_value=None):
            tool = MCPTool(name='test_dynamic', viewset_class=DynamicViewSet, action='create')
            schema = generate_tool_schema(tool)
        
        input_schema = schema['inputSchema']
        
        # Should have body with the dynamic field
        self.assertIn('body', input_schema['properties'])
        body_schema = input_schema['properties']['body']
        self.assertIn('dynamic_field', body_schema['properties'])


class TestDecimalFieldIntegration(unittest.TestCase):
    """Test decimal field schema generation."""
    
    def test_decimal_field_precision_in_schema(self):
        """Test decimal field schema includes precision information in description."""
        
        class PriceSerializer(serializers.Serializer):
            price = serializers.DecimalField(max_digits=10, decimal_places=2)
            high_precision = serializers.DecimalField(max_digits=20, decimal_places=10)
        
        schema = get_serializer_schema(PriceSerializer())
        
        # Check that decimal fields have proper type and description
        price_schema = schema['properties']['price']
        self.assertEqual(price_schema['type'], 'string')
        self.assertIn('Decimal', price_schema['description'])
        self.assertIn('max 10 digits', price_schema['description'])
        self.assertIn('2 decimal places', price_schema['description'])
        
        hp_schema = schema['properties']['high_precision']
        self.assertEqual(hp_schema['type'], 'string')
        self.assertIn('Decimal', hp_schema['description'])
        self.assertIn('max 20 digits', hp_schema['description'])
        self.assertIn('10 decimal places', hp_schema['description'])


class TestCustomDateTimeFormats(unittest.TestCase):
    """Test custom datetime format handling in schema generation."""
    
    def test_custom_datetime_formats_in_schema(self):
        """Test that custom datetime formats are included in field descriptions."""
        
        class EventSerializer(serializers.Serializer):
            start_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
            end_time = serializers.DateTimeField(format='%m/%d/%Y %I:%M %p')
            event_date = serializers.DateField(format='%m/%d/%Y')
            
        schema = get_serializer_schema(EventSerializer())
        
        # Check that custom formats are mentioned in descriptions
        start_schema = schema['properties']['start_time']
        self.assertEqual(start_schema['type'], 'string')
        self.assertEqual(start_schema['format'], 'date-time')  # Always MCP format
        self.assertIn('DateTime in format: %Y-%m-%d %H:%M:%S', start_schema['description'])
        
        end_schema = schema['properties']['end_time']
        self.assertEqual(end_schema['type'], 'string')
        self.assertEqual(end_schema['format'], 'date-time')
        self.assertIn('DateTime in format: %m/%d/%Y %I:%M %p', end_schema['description'])
        
        date_schema = schema['properties']['event_date']
        self.assertEqual(date_schema['type'], 'string')
        self.assertEqual(date_schema['format'], 'date')
        self.assertIn('Date in format: %m/%d/%Y', date_schema['description'])


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
        self.assertEqual(schema['type'], 'object')
        self.assertIn('name', schema['properties'])
        self.assertIn('contact', schema['properties'])
        self.assertIn('emergency_contact', schema['properties'])
        
        # Check nested contact structure
        contact_schema = schema['properties']['contact']
        self.assertEqual(contact_schema['type'], 'object')
        self.assertIn('email', contact_schema['properties'])
        self.assertIn('phone', contact_schema['properties'])
        self.assertIn('address', contact_schema['properties'])
        
        # Check deeply nested address structure
        address_schema = contact_schema['properties']['address']
        self.assertEqual(address_schema['type'], 'object')
        self.assertIn('street', address_schema['properties'])
        self.assertIn('city', address_schema['properties'])
        self.assertIn('state', address_schema['properties'])
        self.assertIn('zip_code', address_schema['properties'])
        
        # Check required fields at different levels
        self.assertIn('name', schema['required'])
        self.assertIn('contact', schema['required'])
        self.assertNotIn('emergency_contact', schema['required'])
        
        self.assertIn('email', contact_schema['required'])
        self.assertIn('address', contact_schema['required'])
        self.assertNotIn('phone', contact_schema['required'])
    
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
        tags_schema = schema['properties']['tags']
        self.assertEqual(tags_schema['type'], 'array')
        self.assertIn('items', tags_schema)
        
        # Check that list item schema is correct
        tag_item_schema = tags_schema['items']
        self.assertEqual(tag_item_schema['type'], 'object')
        self.assertIn('name', tag_item_schema['properties'])
        self.assertIn('color', tag_item_schema['properties'])
        self.assertIn('name', tag_item_schema['required'])
        self.assertNotIn('color', tag_item_schema['required'])


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
        self.assertIn('name', schema['properties'])
        self.assertIn('value', schema['properties'])
        
        # Should NOT include read-only fields
        self.assertNotIn('id', schema['properties'])
        self.assertNotIn('created_at', schema['properties'])
        self.assertNotIn('updated_at', schema['properties'])
        self.assertNotIn('computed_field', schema['properties'])
        
        # Required fields should only include writable required fields
        self.assertIn('name', schema['required'])
        self.assertIn('value', schema['required'])
        self.assertNotIn('id', schema['required'])
        self.assertNotIn('created_at', schema['required'])
    
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
        self.assertEqual(schema['properties'], {})
        self.assertEqual(schema['required'], [])
        self.assertEqual(schema['type'], 'object')
    
    def test_recursive_serializer_handling(self):
        """Test handling of potentially recursive serializer structures."""
        
        class TreeNodeSerializer(serializers.Serializer):
            name = serializers.CharField()
            value = serializers.IntegerField()
            # Note: ListField not yet supported, using CharField for test
            children_ids = serializers.CharField(required=False, help_text="Comma-separated child IDs")
        
        schema = get_serializer_schema(TreeNodeSerializer())
        
        # Should handle the string field correctly
        self.assertIn('children_ids', schema['properties'])
        children_schema = schema['properties']['children_ids']
        self.assertEqual(children_schema['type'], 'string')
        self.assertIn('Comma-separated child IDs', children_schema['description'])
        
        # Should not be required
        self.assertNotIn('children_ids', schema['required'])
        
        # Required fields should include the required ones
        self.assertIn('name', schema['required'])
        self.assertIn('value', schema['required'])


if __name__ == '__main__':
    unittest.main()