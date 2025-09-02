"""Test factories for django-rest-framework-mcp models."""

import factory
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .models import Category, Customer, Order, Product, Tag


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for Django User model."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if create and extracted:
            self.set_password(extracted)
            self.save()

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    class Params:
        """Factory parameters for creating different user types."""

        staff = factory.Trait(is_staff=True)
        superuser = factory.Trait(is_staff=True, is_superuser=True)


class TokenFactory(factory.django.DjangoModelFactory):
    """Factory for Django REST Framework Token model."""

    class Meta:
        model = Token

    user = factory.SubFactory(UserFactory)


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for Category model."""

    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))


class CustomerFactory(factory.django.DjangoModelFactory):
    """Factory for Customer model."""

    class Meta:
        model = Customer

    name = factory.Faker("name")
    email = factory.Faker("email")
    age = factory.Faker("random_int", min=18, max=80)
    is_active = True

    class Params:
        """Factory parameters for creating different customer types."""

        inactive = factory.Trait(is_active=False)
        young = factory.Trait(age=factory.Faker("random_int", min=18, max=25))
        senior = factory.Trait(age=factory.Faker("random_int", min=65, max=80))


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for Product model."""

    class Meta:
        model = Product

    name = factory.Faker("word")
    description = factory.Faker("text", max_nb_chars=200)
    price = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    in_stock = True
    category = factory.SubFactory(CategoryFactory)
    slug = factory.LazyAttributeSequence(
        lambda obj, n: f"{obj.name.lower().replace(' ', '-')}-{1000 + n}"
    )

    class Params:
        """Factory parameters for creating different product types."""

        out_of_stock = factory.Trait(in_stock=False)
        no_category = factory.Trait(category=None)
        no_slug = factory.Trait(slug=None)
        expensive = factory.Trait(
            price=factory.Faker(
                "pydecimal",
                left_digits=5,
                right_digits=2,
                positive=True,
                min_value=1000,
            )
        )
        cheap = factory.Trait(
            price=factory.Faker(
                "pydecimal", left_digits=2, right_digits=2, positive=True, max_value=50
            )
        )


class TagFactory(factory.django.DjangoModelFactory):
    """Factory for Tag model."""

    class Meta:
        model = Tag
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"tag{n}")

    @factory.post_generation
    def products(self, create, extracted, **kwargs):
        """Add products to the tag after creation."""
        if not create:
            return

        if extracted:
            for product in extracted:
                self.products.add(product)


class OrderFactory(factory.django.DjangoModelFactory):
    """Factory for Order model."""

    class Meta:
        model = Order

    customer = factory.SubFactory(CustomerFactory)
    total = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)

    class Params:
        """Factory parameters for creating different order types."""

        large = factory.Trait(
            total=factory.Faker(
                "pydecimal",
                left_digits=5,
                right_digits=2,
                positive=True,
                min_value=1000,
            )
        )
        small = factory.Trait(
            total=factory.Faker(
                "pydecimal", left_digits=2, right_digits=2, positive=True, max_value=50
            )
        )
