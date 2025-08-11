import uuid

from django.core.validators import (
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models


class Post(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Customer(models.Model):
    customer_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(
        max_length=100,
        validators=[MinLengthValidator(2)],
        help_text="Customer's full name (2-100 characters)",
    )
    email = models.EmailField(help_text="Customer's primary email address")
    phone = models.CharField(
        max_length=20,
        validators=[MinLengthValidator(10)],
        help_text="Phone number (minimum 10 characters)",
    )
    account_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.00), MaxValueValidator(99999999.99)],
        help_text="Current account balance (0.00 to 99,999,999.99)",
    )
    credit_score = models.IntegerField(
        validators=[MinValueValidator(300), MaxValueValidator(850)],
        help_text="Credit score (300-850 range)",
    )
    interest_rate = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(30.0)],
        help_text="Interest rate percentage (0.0-30.0%)",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether the customer account is active"
    )
    created_date = models.DateField(
        auto_now_add=True, help_text="Date when customer account was created"
    )
    last_contact_time = models.TimeField(
        null=True, blank=True, help_text="Time of last customer contact (optional)"
    )

    def __str__(self):
        return f"{self.name} ({self.customer_id})"


class Order(models.Model):
    order_number = models.CharField(
        max_length=20, unique=True, help_text="Unique order identifier"
    )
    customer_name = models.CharField(
        max_length=100, help_text="Customer's full name (required)"
    )
    customer_email = models.EmailField(help_text="Customer's email address (required)")
    shipping_address = models.TextField(
        help_text="Complete shipping address (required)"
    )
    notes = models.TextField(
        blank=True, null=True, help_text="Optional order notes or special instructions"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total order amount (calculated from items)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the order was created"
    )

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number if not provided
            import random
            import string

            self.order_number = "ORD-" + "".join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)

    def calculate_total(self):
        """Calculate total from all order items"""
        total = sum(item.quantity * item.unit_price for item in self.items.all())
        self.total_amount = total
        self.save()

    def __str__(self):
        return f"Order {self.order_number} - {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE,
        help_text="The order this item belongs to",
    )
    product_name = models.CharField(
        max_length=200, help_text="Name of the product (required)"
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered (minimum 1, required)",
    )
    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text="Price per unit (minimum 0.01, required)",
    )
    notes = models.TextField(
        blank=True, null=True, help_text="Optional notes for this specific item"
    )

    def __str__(self):
        return f"{self.quantity}x {self.product_name} @ ${self.unit_price}"
