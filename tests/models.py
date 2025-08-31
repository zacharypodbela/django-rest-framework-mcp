"""Test models for django-rest-framework-mcp."""

from django.db import models


class RESTFrameworkMCPModel(models.Model):
    """Base for test models that sets app_label."""

    class Meta:
        app_label = "tests"
        abstract = True


class Customer(RESTFrameworkMCPModel):
    """Test model for Customer."""

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    age = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(RESTFrameworkMCPModel):
    """Test model for Category."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Product(RESTFrameworkMCPModel):
    """Test model for Product."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    in_stock = models.BooleanField(default=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="products",
    )
    slug = models.SlugField(unique=True, null=True, blank=True)

    def __str__(self):
        return self.name


class Order(RESTFrameworkMCPModel):
    """Test model for Order."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="orders"
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} for {self.customer.name}"


class Tag(RESTFrameworkMCPModel):
    """Test model for Tag."""

    name = models.CharField(max_length=50, unique=True)
    products = models.ManyToManyField(Product, related_name="tags", blank=True)

    def __str__(self):
        return self.name
