from rest_framework import viewsets
from djangorestframework_mcp.decorators import mcp_tool

from blog.models import Post
from blog.serializers import PostSerializer

@mcp_tool()
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
