from rest_framework import viewsets
from djangorestframework_mcp.decorators import mcp_viewset

from blog.models import Post
from blog.serializers import PostSerializer

@mcp_viewset()
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer

    # This tests: 
    # - Custom implementations of CRUD actions on ModelViewSet run
    # - Custom logic using is_mcp_request works
    def create(self, request, *args, **kwargs):
        if request.is_mcp_request and request.data.get('content'):
            # Append text to the end of the content noting it was created via MCP
            request.data['content'] += "\n\n*Created via MCP*"

        return super().create(request, *args, **kwargs)