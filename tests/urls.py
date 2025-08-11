"""Test URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomerViewSet, ProductViewSet

router = DefaultRouter()
router.register(r"customers", CustomerViewSet)
router.register(r"products", ProductViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
    path("mcp/", include("djangorestframework_mcp.urls")),
]
