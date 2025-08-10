from cProfile import label
from rest_framework import serializers

from blog.models import Post

class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = "__all__"

# DEMO: Add label and/or help_text to fields to give the LLM more context and increase its ability to use the tool
class CreatePostSerializer(PostSerializer):
    add_created_on_footer = serializers.BooleanField(
        required=False, 
        default=False,
        label='Add "Created on" Footer',
        help_text='If true, appends the creation date to the end of the content',
    )

class BulkPostSerializer(serializers.ListSerializer):
    child = PostSerializer()