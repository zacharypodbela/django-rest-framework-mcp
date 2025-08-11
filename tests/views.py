"""Test views for django-rest-framework-mcp."""

from rest_framework import viewsets

from djangorestframework_mcp.decorators import mcp_viewset

from .models import Customer, Product
from .serializers import CustomerSerializer, ProductSerializer


@mcp_viewset()
class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for Customer model with MCP support."""

    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


@mcp_viewset(basename="products")
class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product model with custom MCP name."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
