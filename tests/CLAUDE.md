# Test Organization Standards

This document establishes standards for writing and organizing tests in the `django-rest-framework-mcp` project.

### Test Files (files that begin with `test_`)

- Each implementation file (`schema.py`, `views.py`, etc.) has a single corresponding file (`test_schema.py`, `test_mcp_views.py`, etc.) containing all unit tests for the file.
- All integration tests (End-to-end MCP protocol tests with real HTTP requests) live in single file: `test_integration.py`.
- All regression tests (ensuring normal API calls continues to work) live in single file: `test_regression.py`

### Test Fixtures

- This project uses **Factory Boy** for creating test data. All model creation should use factories instead of direct `.objects.create()` calls. See the list of available factories in defined in `tests/factories.py`.
- Reusable fixtures for common test scenarios should live in `models.py`, `serializers.py`, `views.py`. This makes it easy for future developers to discover and leverage existing fixtures.
- Leverage existing fixtures whenever possible. If you find yourself reusing a fixture that was previously defined inline, consider moving it to the corresponding common fixtures file.
- Fixtures should only be defined inline if they are used in a single test class, highly specialized for one specific test scenario (would not be meaningful to other tests), or require runtime definition (ex: you don't want the decorator to run until the test runs).
- When defining fixtures inline they must be a part of the test class that they are being used in. You must NOT define them at the root of the file:

```python
# YES:
class ChoiceFieldIntegrationTests(TestCase):
    def setUp():
        class TagListSerializer(serializers.Serializer):
              tags = serializers.ListField(
                  child=serializers.CharField(max_length=50), min_length=1, max_length=10
              )

        @mcp_viewset(basename="tags")
        class TagListViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
            serializer_class = TagListSerializer

# NO!:
class TagListSerializer(serializers.Serializer):
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50), min_length=1, max_length=10
    )

@mcp_viewset(basename="tags")
class TagListViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    serializer_class = TagListSerializer
```

### Other Supporting Files

- **`conftest.py`** - Pytest configuration and Django setup
- **`urls.py`** - URL routing for test scenarios
- **`factories.py`** - Factory Boy factories for test data creation
