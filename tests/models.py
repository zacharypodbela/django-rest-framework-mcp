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


class RequiredFieldsTestModel(RESTFrameworkMCPModel):
    """Test model with various field configurations for testing required field logic."""

    # Case 1: Basic required field (no blank/null, no default)
    basic_required = models.CharField(max_length=100)

    # Case 2: Field with default (should not be required)
    with_default = models.CharField(max_length=100, default="default_value")

    # Case 3: Field with blank=True (should not be required)
    with_blank = models.CharField(max_length=100, blank=True)

    # Case 4: Field with null=True (should not be required for non-char fields)
    with_null = models.IntegerField(null=True)

    # Case 5: Field with both blank=True and null=True (should not be required)
    with_blank_and_null = models.CharField(max_length=100, blank=True, null=True)

    # Case 6: BooleanField with default (should not be required)
    bool_with_default = models.BooleanField(default=True)

    # Case 7: Field with unique constraint but also blank/null (should NOT be required)
    # Per DRF docs: unique fields are required UNLESS they have blank=True or null=True
    unique_with_blank_null = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )

    # Case 7b: Field with unique constraint, no blank/null (should be required)
    unique_no_blank = models.CharField(max_length=100, unique=True)

    # Case 8: Field with unique constraint AND default (should not be required)
    unique_with_default = models.CharField(
        max_length=100, unique=True, default="unique_default", blank=True, null=True
    )

    # Case 9: AutoField (should be read-only)
    auto_field = models.AutoField(primary_key=True)

    # Case 10: Field with auto_now_add (should be read-only)
    created_at = models.DateTimeField(auto_now_add=True)

    # Case 11: Field with auto_now (should be read-only)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tests"
