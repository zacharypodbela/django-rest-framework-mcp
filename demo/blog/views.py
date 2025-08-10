from time import timezone
import mcp
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset

from blog.models import Post
from blog.serializers import CreatePostSerializer, PostSerializer

# DEMO: Tools are created for all CRUD actions on ModelViewSet
@mcp_viewset()
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer

    # DEMO: For overridden CRUD actions, use input_serializer if the input is different from the serializer_class
    @mcp_tool(
        name='create_posts_via_mcp', 
        title='Create Posts via MCP', 
        description='Create new blog posts. "Created via MCP" will be appended to the end of the content automatically',
        input_serializer=CreatePostSerializer,
    )
    def create(self, request, *args, **kwargs):
        # DEMO: Custom logic using is_mcp_request works
        if request.is_mcp_request and request.data.get('content'):
            # Append text to the end of the content noting it was created via MCP
            request.data['content'] += "\n\n*Created via MCP*"

        if request.data.get('add_created_on_footer'):
            request.data['content'] += f"\n\n*Created on {timezone.now().date()}*"

        return super().create(request, *args, **kwargs)

    # DEMO: Register custom actions with no input
    @mcp_tool(
        name='get_recent_posts',
        title='Get Recent Posts',
        description='Retrieves the 5 most recently created blog posts',
        input_serializer=None
    )
    @action(detail=False, methods=['get'])
    def recent_posts(self, request):
        # Returns the 5 most recently created posts
        recent_posts = self.get_queryset().order_by('-created_at')[:5]
        serializer = self.get_serializer(recent_posts, many=True)
        return Response(serializer.data)

    # DEMO: Register custom actions with custom input
    @mcp_tool(
        name='merge_posts',
        title='Merge Posts',
        description='Merges the content of a new post with a user-provided prompt',
        input_serializer=PostSerializer(many=True)
    )
    @action(detail=False, methods=['post'])
    def merge(self, request):
        # Takes in an array of post objects and combines their content and titles into a new post.
        posts = request.data['posts']
        combined_content = "\n\n".join([post['content'] for post in posts])
        combined_titles = "\n\n".join([post['title'] for post in posts])
        post = Post.objects.create(content=combined_content, title=combined_titles)
        return Response(PostSerializer(post).data)