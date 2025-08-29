"""Test URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuthenticatedViewSet,
    CustomAuthViewSet,
    CustomerViewSet,
    CustomPermissionViewSet,
    MultipleAuthViewSet,
    ProductViewSet,
    UnauthenticatedViewSet,
)

router = DefaultRouter()
router.register(r"customers", CustomerViewSet)
router.register(r"products", ProductViewSet)
router.register(r"auth/authenticated", AuthenticatedViewSet, basename="authenticated")
router.register(r"auth/multipleauth", MultipleAuthViewSet, basename="multipleauth")
router.register(
    r"auth/unauthenticated", UnauthenticatedViewSet, basename="unauthenticated"
)
router.register(r"auth/customauth", CustomAuthViewSet, basename="customauth")
router.register(
    r"auth/custompermission", CustomPermissionViewSet, basename="custompermission"
)

urlpatterns = [
    path("api/", include(router.urls)),
    path("mcp/", include("djangorestframework_mcp.urls")),
]
