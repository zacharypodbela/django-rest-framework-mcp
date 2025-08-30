from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow authors of a post to edit or delete it.
    Everyone can list and retrieve posts.
    Only authenticated users can create posts.
    """

    # DEMO: We strongly encourage using the message property in custom permissions to give the LLM more context on why permission was denied
    message = "You can only edit posts that you are the author of."

    def has_permission(self, request, view):
        # Allow list and retrieve for everyone (including anonymous)
        if view.action in ["list", "retrieve"]:
            return True

        # Require authentication for create, update, delete actions
        if view.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "bulk_create",
            "reverse",
        ]:
            return request.user and request.user.is_authenticated

        # This should never run because all actions are listed above
        # We default to False in case new actions are added and developers forget to implement permissions for them.
        return False

    # DEMO: Object-level permissions will still be enforced for MCP requests
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if view.action in ["retrieve"]:
            return True

        # Write permissions are only allowed to the author of the post
        if view.action in ["update", "partial_update", "destroy", "reverse"]:
            # Only the author can edit or delete
            return obj.author == request.user

        # This should never run because all detail=True actions are listed above
        # We default to False in case new actions are added and developers forget to implement permissions for them.
        return False
