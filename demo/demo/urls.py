from django.urls import include, path
from django.contrib import admin
from rest_framework import routers

from blog.views import PostViewSet, CustomerViewSet, OrderViewSet

router = routers.DefaultRouter()
router.register(r'posts', PostViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'orders', OrderViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('admin/', admin.site.urls),
    path('mcp/', include('djangorestframework_mcp.urls'))
]