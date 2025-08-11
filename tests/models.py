"""Test models for django-rest-framework-mcp."""

from django.db import models


class RESTFrameworkMCPModel(models.Model):
    """Base for test models that sets app_label."""
    
    class Meta:
        app_label = 'tests'
        abstract = True


class Customer(RESTFrameworkMCPModel):
    """Test model for Customer."""
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    age = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Product(RESTFrameworkMCPModel):
    """Test model for Product."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    in_stock = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name