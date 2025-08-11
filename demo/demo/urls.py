from blog.views import CustomerViewSet, OrderViewSet, PostViewSet
from django.contrib import admin
from django.urls import include, path
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r"posts", PostViewSet)
router.register(r"customers", CustomerViewSet)
router.register(r"orders", OrderViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("admin/", admin.site.urls),
    path("mcp/", include("djangorestframework_mcp.urls")),
]
