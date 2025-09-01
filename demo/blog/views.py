from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from blog.models import Customer, Order, Post
from blog.permissions import IsAuthorOrReadOnly
from blog.serializers import (
    BulkPostSerializer,
    CreatePostSerializer,
    CustomerSerializer,
    OrderSerializer,
    PostSerializer,
)
from djangorestframework_mcp.decorators import mcp_tool, mcp_viewset


# DEMO: Tools are created for all CRUD actions on ModelViewSet
@mcp_viewset()
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    # DEMO: permissions set on the ViewSet will be applied to both API and MCP requests
    permission_classes = [IsAuthorOrReadOnly]

    def get_serializer_class(self):
        if self.action == "bulk_create":
            return BulkPostSerializer
        return PostSerializer

    def perform_create(self, serializer):
        """Automatically set the author to the current user when creating a post."""
        # Check if this is a bulk create (ListSerializer)
        if hasattr(serializer, "child"):
            # This is a ListSerializer for bulk operations
            # We need to set the author for each post in the validated data
            for post_data in serializer.validated_data:
                post_data["author"] = self.request.user
            serializer.save()
        else:
            # This is a regular single post creation
            serializer.save(author=self.request.user)

    # DEMO: For overridden CRUD actions, use input_serializer if the input is different from the serializer_class
    # DEMO: Use is_mcp_request to run certain logic only on MCP requests
    @mcp_tool(
        name="create_posts_via_mcp",
        title="Create Posts via MCP",
        description='Create new blog posts. "Created via MCP" will be appended to the end of the content automatically',
        input_serializer=CreatePostSerializer,
    )
    def create(self, request, *args, **kwargs):
        # Check if this is an MCP request (need to use getattr since the attribute is only set on MCP requests)
        if getattr(request, "is_mcp_request", False) and request.data.get("content"):
            # Append text to the end of the content noting it was created via MCP
            request.data["content"] += "\n\n*Created via MCP*"

        if request.data.pop("add_created_on_footer", False):
            request.data["content"] += f"\n\n*Created on {timezone.now().date()}*"

        return super().create(request, *args, **kwargs)

    # DEMO: Register custom actions with no input
    @mcp_tool(description="Reverses a Post's title and content", input_serializer=None)
    @action(detail=True, methods=["post"])
    def reverse(self, request, *args, **kwargs):
        post = self.get_object()
        post.title = post.title[::-1]
        post.content = post.content[::-1]
        post.save()
        return Response(PostSerializer(post).data)

    # DEMO: Register custom actions with custom input
    # DEMO: Support for ListSerializers (array of objects) as input
    @mcp_tool(
        name="bulk_create_posts",
        title="Bulk Create Posts",
        description="Creates multiple blog posts in a single request",
        input_serializer=BulkPostSerializer,
    )
    @action(detail=False, methods=["post"])
    def bulk_create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


# DEMO: Selective action registration with custom basename
@mcp_viewset(basename="customer_mgmt", actions=["list", "retrieve", "deactivate"])
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    # DEMO: Custom action for deactivating customers (business logic that's safe for MCP)
    @mcp_tool(
        name="deactivate_customer",
        title="Deactivate Customer",
        description="Deactivates a customer account by setting is_active to False",
        input_serializer=None,
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        customer = self.get_object()
        customer.is_active = False
        customer.save()
        return Response(
            {
                "message": f"Customer {customer.name} has been deactivated",
                "customer": CustomerSerializer(customer).data,
            }
        )


# DEMO: Nested serializers and required/optional field inference
@mcp_viewset(actions=["create", "list", "retrieve"])
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().prefetch_related("items")
    serializer_class = OrderSerializer
