from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

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

    # This tests:
    # - Automatic detection and registry of custom actions
    @action(detail=False, methods=['get'])
    def recent_posts(self, request):
        # Returns the 5 most recently created posts
        recent_posts = self.get_queryset().order_by('-created_at')[:5]
        serializer = self.get_serializer(recent_posts, many=True)
        return Response(serializer.data)

@mcp_viewset()
class DashboardViewSet(viewsets.ViewSet):

    # This tests:
    # - Customizing tool metadata for better LLM performance
    @mcp_tool(name='blog_stats', title='Blog Statistics', description='Get blog statistics')
    @action(detail=False, methods=['get'])
    def stats(self, request):
        # Example action to return some dashboard statistics
        data = {
            'total_posts': Post.objects.count(),
        }
        return Response(data)