"""Test serializers for django-rest-framework-mcp."""

from rest_framework import serializers
from .models import Customer, Product


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model."""
    
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'age', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""
    
    class Meta:
        model = Product
        fields = '__all__'


# Test serializers for list inputs and validation testing

class SimpleItemSerializer(serializers.Serializer):
    """Simple serializer for testing list inputs."""
    name = serializers.CharField(max_length=100)
    value = serializers.IntegerField()
    is_active = serializers.BooleanField(default=True)


class SimpleItemListSerializer(serializers.ListSerializer):
    """List serializer for testing list inputs."""
    child = SimpleItemSerializer()


class StrictSerializer(serializers.Serializer):
    """Strict serializer for testing validation errors."""
    name = serializers.CharField(max_length=5, required=True)  # Very short for testing
    value = serializers.IntegerField(min_value=0, required=True)


class StrictListSerializer(serializers.ListSerializer):
    """List serializer with strict validation."""
    child = StrictSerializer()


class NestedItemSerializer(serializers.Serializer):
    """Nested serializer for testing nested structures."""
    id = serializers.IntegerField()
    name = serializers.CharField()


class ContainerSerializer(serializers.Serializer):
    """Container serializer with nested lists."""
    title = serializers.CharField()
    items = NestedItemSerializer(many=True)