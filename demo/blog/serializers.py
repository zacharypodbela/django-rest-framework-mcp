from rest_framework import serializers

from blog.models import Customer, Order, OrderItem, Post


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
        help_text="If true, appends the creation date to the end of the content",
    )


class BulkPostSerializer(serializers.ListSerializer):
    child = PostSerializer()


# DEMO: Show all primitive field types with constraints and help_text
class CustomerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=100,
        min_length=2,
        help_text="Customer's full name (2-100 characters)",
        label="Full Name",
    )
    email = serializers.EmailField(
        help_text="Customer's primary email address", label="Email Address"
    )
    phone = serializers.CharField(
        max_length=20,
        min_length=10,
        help_text="Phone number (minimum 10 characters)",
        label="Phone Number",
    )
    account_balance = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.00,
        max_value=99999999.99,
        help_text="Current account balance (0.00 to 99,999,999.99)",
        label="Account Balance",
    )
    credit_score = serializers.IntegerField(
        min_value=300,
        max_value=850,
        help_text="Credit score (300-850 range)",
        label="Credit Score",
    )
    interest_rate = serializers.FloatField(
        min_value=0.0,
        max_value=30.0,
        help_text="Interest rate percentage (0.0-30.0%)",
        label="Interest Rate",
    )
    is_active = serializers.BooleanField(
        default=True,
        help_text="Whether the customer account is active",
        label="Active Status",
    )
    created_date = serializers.DateField(
        read_only=True,
        help_text="Date when customer account was created",
        label="Creation Date",
    )
    last_contact_time = serializers.TimeField(
        required=False,
        allow_null=True,
        help_text="Time of last customer contact (optional)",
        label="Last Contact Time",
    )
    customer_id = serializers.UUIDField(
        read_only=True, help_text="Unique customer identifier", label="Customer ID"
    )

    class Meta:
        model = Customer
        fields = "__all__"


# DEMO: Nested serializers for writing complex objects
class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(
        max_length=200, help_text="Name of the product (required)", label="Product Name"
    )
    quantity = serializers.IntegerField(
        min_value=1,
        help_text="Quantity ordered (minimum 1, required)",
        label="Quantity",
    )
    unit_price = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0.01,
        help_text="Price per unit (minimum 0.01, required)",
        label="Unit Price",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional notes for this specific item",
        label="Item Notes",
    )

    class Meta:
        model = OrderItem
        fields = ["product_name", "quantity", "unit_price", "notes"]


# DEMO: Required vs optional fields and nested serializer writing
class OrderSerializer(serializers.ModelSerializer):
    # Required fields (no default, required=True is implicit for CharField/EmailField)
    customer_name = serializers.CharField(
        max_length=100,
        help_text="Customer's full name (required)",
        label="Customer Name",
    )
    customer_email = serializers.EmailField(
        help_text="Customer's email address (required)", label="Customer Email"
    )
    shipping_address = serializers.CharField(
        help_text="Complete shipping address (required)", label="Shipping Address"
    )

    # Optional field (explicitly marked as not required)
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional order notes or special instructions",
        label="Order Notes",
    )

    # Nested serializer for writing order items
    items = OrderItemSerializer(
        many=True,
        help_text="List of items to include in this order (required, minimum 1 item)",
        label="Order Items",
    )

    # Read-only fields
    order_number = serializers.CharField(read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number",
            "customer_name",
            "customer_email",
            "shipping_address",
            "notes",
            "items",
            "total_amount",
            "created_at",
        ]

    def create(self, validated_data):
        """Handle nested creation of order and items"""
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)

        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)

        # Calculate and save total
        order.calculate_total()
        return order
