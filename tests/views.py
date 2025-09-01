"""Test views for django-rest-framework-mcp."""

from rest_framework import viewsets
from rest_framework.authentication import (
    BasicAuthentication,
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

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


# Authentication test helpers
class CustomAuthentication(TokenAuthentication):
    """Custom authentication class for testing."""

    keyword = "Custom"


class CustomPermission(IsAuthenticated):
    """Custom permission class for testing."""

    message = "Custom permission denied"


class AlwaysDenyPermission(BasePermission):
    """Permission class that always denies but doesn't require auth."""

    message = "Custom permission denied"

    def has_permission(self, request, view):
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied(detail=self.message)


# Authentication test ViewSets
@mcp_viewset()
class AuthenticatedViewSet(viewsets.GenericViewSet):
    """Test ViewSet with authentication requirements."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response([{"id": 1, "name": "Authenticated Item"}])


@mcp_viewset()
class MultipleAuthViewSet(viewsets.GenericViewSet):
    """Test ViewSet with multiple authentication methods."""

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
        BasicAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response([{"id": 1, "name": "Multi-auth Item"}])


@mcp_viewset()
class UnauthenticatedViewSet(viewsets.GenericViewSet):
    """Test ViewSet without authentication requirements."""

    def list(self, request):
        return Response([{"id": 1, "name": "Public Item"}])


@mcp_viewset()
class CustomAuthViewSet(viewsets.GenericViewSet):
    """Test ViewSet with custom authentication and permission classes."""

    authentication_classes = [CustomAuthentication]
    permission_classes = [CustomPermission]

    def list(self, request):
        return Response([{"id": 1, "name": "Custom Auth Item"}])


@mcp_viewset()
class CustomPermissionViewSet(viewsets.GenericViewSet):
    """Test ViewSet with custom permission that always denies."""

    permission_classes = [AlwaysDenyPermission]

    def list(self, request):
        return Response([{"id": 1, "name": "Should never reach here"}])
