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