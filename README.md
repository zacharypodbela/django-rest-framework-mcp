# Django REST Framework MCP

[![PyPI version](https://badge.fury.io/py/django-rest-framework-mcp.svg)](https://badge.fury.io/py/django-rest-framework-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/django-rest-framework-mcp.svg)](https://pypi.org/project/django-rest-framework-mcp/)

> ⚠️ **Alpha Release**: This library is in early alpha stage. APIs may change and there may be bugs. Use with caution in production environments. We welcome feedback and contributions!

`django-rest-framework-mcp` allows you to quickly build MCP servers that expose your Django Rest Framework APIs as tools for LLMs and agentic applications to work with.

## Quick Start

1. Install the package:

```bash
pip install django-rest-framework-mcp
```

2. Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your other apps
    'djangorestframework_mcp',
]
```

3. Add the MCP endpoint to your `urls.py`:

```python
urlpatterns = [
    # ... your other URL patterns
    path('mcp/', include('djangorestframework_mcp.urls')),
]
```

4. Transform any DRF ViewSet into MCP tools with a single decorator:

```python
from djangorestframework_mcp.decorators import mcp_viewset

@mcp_viewset()
class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
```

When `@mcp_viewset` is applied to a ViewSet class that inherits from `GenericViewSet` (such as `ModelViewSet` or `ReadOnlyModelViewSet`), any of the following methods that are defined will be automatically exposed as MCP tools:

- `list` -> List customers with `customers_list` tool.
- `retrieve` -> Retrieve a customer with `customers_retrieve` tool.
- `create` -> Create new customers with `customers_create` tool.
- `update` -> Update customers with `customers_update` tool. (All fields must be passed in)
- `partial_update` -> Update customers with `customers_partial_update` tool. (A subset of fields can be passed in)
- `destroy` -> Delete customers with `customers_destroy` tool.

For each tool the library automatically:

- Generates tool schemas from your DRF serializers
- Preserves your existing permissions, authentication, and filtering
- Returns context rich error messages to guide LLMs

(See: _Custom Actions_ below for more info on how to expose additional endpoints you created using the `@action` decorator as tools).

5. Connect any MCP client to `http://localhost:8000/mcp/` and try it out!

### Important Differences between MCP Requests and API Requests

MCP requests do not go through the full DRF request lifecycle.

View lifecycle methods that will be called:

- **`initial(request, args, kwargs)`** will be called.
  - If your view runs the default implementation in `APIView` (either by not overriding this function or calling `super().initial`), this includes calling `perform_authentication`, `check_permissions`, `check_throttles`, and `determine_version`.
  - While `perform_content_negotiation` would also be called, the `Request` object will not have a `negotiator` and the only value for `parsers` will be `JSONParser()` since MCP/JSON-RPC dictates the input and output format.

View lifecycle methods that won't be called:

- **`dispatch(request, args, kwargs)`** will not be called.
- **`initialize_request(request, args, kwargs)`** will not be called. We do create a `rest_framework.requests.Request` from the `django.http.HttpRequest`, but not using this handler.
- **`finalize_response(request, response, args, kwargs)`** will not be called.
- **`handle_exception(exc)`** will not be called in the event of an exception\*.

In addition, since the `request` was not the result of an incoming API call, it will be missing any API specific properties, such as `method`, `path`, or `path_info`.

## Connecting a STDIO MCP Client

Right now, the MCP server is only open to HTTP transport. To support stdio transport, you'll need a bridge. We recommend [mcp-remote](https://github.com/geelen/mcp-remote).

### Example: Connect to Claude Desktop

Follow these instructions to use `mcp-remote` to connect to Claude Desktop:

1. Install mcp-remote: `npm install -g mcp-remote`

2. Open Claude MCP Desktop Configuration by going to Settings > Developer > Edit Config and add your server configuration:

```json
{
  "mcpServers": {
    "my-django-mcp": {
      "command": "node",
      "args": [
        "path/to/mcp-remote",
        "http://localhost:8000/mcp/",
        "--transport",
        "http-only"
      ]
    }
  }
}
```

3. Restart Claude Desktop and test your tools

**Development Tip:** LLMs can be surprisingly effective at “manually” testing your MCP tools and uncovering bugs. In Claude Desktop, try a prompt like: _"I'm developing a new set of MCP tools locally. Please extensively test them — including coming up with complex edge cases to try - and look for unexpected behavior or bugs. Make at least 30 tool calls."_

## Advanced Configuration

### Custom Actions

Custom actions, created with the `@action` decorator, require explicit schema definition since there aren't standard input defaults like with CRUD endpoints. To create a tool from a custom action, apply the `@mcp_tool` decorator and pass in an `input_serializer`:

```python
from djangorestframework_mcp.decorators import mcp_viewset, mcp_tool

class GenerateInputSerializer(serializers.Serializer):
    user_prompt = serializers.CharField(help_text="The prompt to send to the LLM")

@mcp_viewset()
class ContentViewSet(viewsets.ViewSet):
    @mcp_tool(input_serializer=GenerateInputSerializer)
    @action(detail=False, methods=['post'])
    def generate(self, request):
        user_prompt = request.data['user_prompt']
        llm_response = call_llm(user_prompt)
        return Response({'llm_response': llm_response})
```

For custom actions that don't require input, set `input_serializer=None`:

```python
@mcp_tool(input_serializer=None)  # No input needed
@action(detail=False, methods=['get'])
def recent_posts(self, request):
    recent_posts = Post.objects.filter(created_at__gte=timezone.now() - timedelta(days=7))
    serializer = PostSerializer(recent_posts, many=True)
    return Response(serializer.data)
```

For CRUD actions (`list`, `retrieve`, `create`, `update`, `partial_update`, `destroy`), `input_serializer` is **optional**. The library will default to inferring schemas from the ViewSet's `serializer_class` if `input_serializer` is not specified. You'll want to use this optional parameter if you've written custom business logic that changes the input schema of a CRUD endpoint.

```python
class ExtendedPostSerializer(PostSerializer): # Inherits and extends standard CRUD serializer
    add_created_at_footer = serializers.BooleanField(help_text="Setting to true appends the author name")

@mcp_tool(input_serializer=ExtendedPostSerializer)
def create(self, request, *args, **kwargs):
    if request.data.get('add_created_at_footer'):
        # Append text to the end of the content noting it was created via MCP
        request.data['content'] += f"\n\n*Created by {request.user.name}*"

    return super().create(request, *args, **kwargs)
```

### Selective Action Registration

If you don't want to create a tool from every action of a ViewSet, you can whitelist which actions to expose by passing an `actions` array to `@mcp_viewset`:

```python
@mcp_viewset(actions=['banish', 'list'])
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def banish(self, request, pk=None):
        # ... Business Logic
```

### Custom Tool Names and Descriptions

You can customize the names, titles, and descriptions of individual actions using the `@mcp_tool` decorator. (NOTE: The `@mcp_tool` decorator only works when the ViewSet class is also decorated with `@mcp_viewset`. Using `@mcp_tool` alone will not register any MCP tools.)

```python
@mcp_viewset()
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @mcp_tool(
        name="get_customer_details",
        title="Get Customer Details",
        description="Retrieve detailed information about a specific customer by their ID"
    )
    def retrieve(self, request, pk=None):
        return super().retrieve(request, pk)
```

### MCP-Specific Overrides

Sometimes you want different behavior for MCP requests vs regular API requests. You have two options for achieving this.

#### Option 1: Inheritance (Recommended)

Create a dedicated ViewSet for MCP that inherits from your existing ViewSet.

```python
@mcp_viewset()
class CustomerMCPViewSet(CustomerViewSet):
    # Limit MCP clients to active customers only
    queryset = super().get_queryset().filter(is_active=True)
    # Use a simplified serializer for MCP clients
    serializer_class = CustomerMCPSerializer
    # ... everything else is inherited

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
```

#### Option 2: Using Control Flows

Use the `request.is_mcp_request` property to conditionally modify behavior within your existing ViewSet.

```python
@mcp_viewset()
class CustomerViewSet(viewsets.ModelViewSet):
    def get_queryset(self, request):
        queryset = Customer.objects.all()

        # Limit MCP clients to active customers only
        if request.is_mcp_request:
            queryset = queryset.filter(is_active=True)

        return queryset

    def get_serializer_class(self, request):
        # Use a simplified serializer for MCP clients
        if request.is_mcp_request:
            return CustomerMCPSerializer
        return CustomerSerializer
```

## Testing Your MCP Tools

The library provides test utilities to verify your MCP tools work correctly:

```python
from django.test import TestCase
from djangorestframework_mcp.test import MCPClient

class CustomerMCPTests(TestCase):
    def test_list_customers(self):
        # Create test data
        Customer.objects.create(name="Alice", email="alice@example.com")
        Customer.objects.create(name="Bob", email="bob@example.com")

        # Create MCP client and call tool
        client = MCPClient()
        result = client.call_tool("customers_list")

        # Assert the response
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_error_handling(self):
        # Test validation errors
        client = MCPClient()
        result = client.call_tool("create_customers", {"body": {}})

        self.assertTrue(result.get('isError'))
        self.assertIn('Body is required', result['content'][0]['text'])
```

### Array Inputs

For endpoints that accept arrays of data (like bulk operations), create a `ListSerializer` subclass and use it as your `input_serializer`:

```python
class CustomerListSerializer(serializers.ListSerializer):
    child = CustomerSerializer()

@mcp_viewset()
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @mcp_tool(input_serializer=CustomerListSerializer)
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
      # ... request.data will be an array of Posts
```

## Roadmap

### Currently Supported DRF Features

**MVP Features (Available Now)**

- ✅ Automatically generates tools for all actions on any ViewSet
  - ✅ CRUD actions (list/retrieve/create/update/partial_update/destroy)
  - ✅ Custom actions (created with @action decorator)
- ✅ Implements [MCP protocol](https://modelcontextprotocol.io/) for Initialization and Tools (discovery and invocation)
  - _[Coming later: support for resources, prompts, notifications]_
- ✅ HTTP transport via `/mcp` endpoint
  - _[Coming later: sse & stdio]_
- ✅ Auto-generated tool input/output schemas from DRF serializers
  - ✅ Required/optional inferred automatically
  - ✅ Constraints (min/max length, min/max value) inferred automatically
  - ✅ help_text/label passed back to MCP Client as parameter title and description
  - ✅ Primitive types (string/int/float/bool/datetime/date/time/UUID)
  - ✅ Nested Serializers
  - ✅ ListSerializers
  - ✅ Formatting inferred and passed back to MCP Client as part of field description.
  - _[Coming later: additional advanced types]_
- ✅ Test utilities for MCP tools

### Future Roadmap

- Resource and prompt discovery and invocation as laid out in [MCP Protocol](https://modelcontextprotocol.io/)

- Notifications as laid out in [MCP Protocol](https://modelcontextprotocol.io/)

- Browsable UI of MCP tool, resource, and prompts discovery and invocation

- Decorate custom validators with instructions (which will be shared with the MCP Client)

- Relationship fields (PK/Slug/StringRelated)

- Arrays/objects/JSONB fields

- Enum fields

- Support for other kwargs besides the lookup_url_kwarg.

- Permission requirements advertised in tool schema

- Basic OpenAPI schema export for MCP tools

- Filtering via DjangoFilterBackend (filterset_fields/class)

- SearchFilter support (search_fields)

- OrderingFilter support (ordering_fields)

- Pagination (LimitOffsetPagination/PageNumberPagination/CursorPagination)

- Throttling (UserRateThrottle/AnonRateThrottle/ScopedRateThrottle)

- Versioning (URLPathVersioning/NamespaceVersioning/AcceptHeaderVersioning/HostNameVersioning)

- Non-JSON Inputs (FormParser/MultiPartParser/FileUploadParser) [Not sure if this is even possible]

- Built-in /mcp auth via OAuth2

- Standalone stdio MCP server

- HyperlinkedModelSerializer, HyperlinkedIdentityField support [It might actually make most sense to do something like this as the default when we get to supporting Relationships. Giving the LLM the context on the relevant tools it can use to operate on the object along with it's FK / info.]

- Custom classes - pagination, permission, authentication, etc.

- Object-level permissions (DjangoObjectPermissions)

- Model permissions (DjangoModelPermissions)

- Depth-based serialization support

- Metadata classes (SimpleMetadata)

- Async views/endpoints support

- Streaming responses [Not sure if this is even possible]

- Caching headers support

## API Reference

### Decorators

#### `@mcp_viewset(basename=None, actions=None)`

Class decorator for ViewSets that inherit from `GenericViewSet` to expose actions as MCP tools. Compatible with `ModelViewSet`, `ReadOnlyModelViewSet`, or any other ViewSets that inherit from `GenericViewSet`.

**Parameters:**

- `basename` (str, optional): Custom base name for the tool set. Used to autogenerate tool names if custom ones are not provided. Defaults to the ViewSet's model name.
- `actions` (list, optional): List of specific actions to expose. If None, all available actions are exposed.

#### `@mcp_tool(name=None, title=None, description=None, input_serializer=...)`

Method decorator to register custom ViewSet actions and/or customize action MCP exposure. Custom actions (non-CRUD methods) must also be decorated with `@action`.

**Parameters:**

- `name` (str, optional): Custom name for this specific action. If not provided, will be auto-generated from the action name.
- `title` (str, optional): Human-readable title for the tool.
- `description` (str, optional): Description for this specific action.
- `input_serializer` (Serializer class or None, required for custom actions): Serializer class for input validation. Required for custom actions (can be None). Optional for CRUD actions.

### Extended HttpRequest Properties

#### `.is_mcp_request`

Check if the current request is coming from an MCP client.

### Test Utilities

#### `MCPClient`

Test client for interacting with MCP servers in your tests. Extends `django.test.Client` to handle MCP protocol communication.

**Parameters:**

- `mcp_endpoint` (str, optional): The URL path to the MCP server endpoint. Defaults to 'mcp/' to match the library's default routing.
- `auto_initialize` (bool, optional): Whether to automatically perform the MCP initialization handshake. Set to False if you need to test initialization behavior explicitly. Defaults to True.
- `*args` / `**kwargs`: Additional arguments passed to Django's Client constructor (e.g., `HTTP_HOST`, `enforce_csrf_checks`, etc.).

**Methods:**

- `call_tool(tool_name, arguments=None)`: Execute an MCP tool and return the result
- `list_tools()`: Discover all available MCP tools from the server
- `initialize()`: Perform MCP initialization handshake (done automatically unless `auto_initialize=False`)

## Contributing

We welcome contributions!

### Project Structure

Unsurprisingly, we're using AI tools pretty actively in our development workflows, and so the project structure has been optimized for collaboration by both humans and agents.

- **`djangorestframework_mcp/`**: The library source code
- **`tests/`**: All tests (unit and integration)
- **`demo/`**: A working Django app for manual testing
- **`/internal-docs`**: Documentation about the implementation, strategy, and/or goals of the `django-rest-framework-api` project.
- **`external-docs/`**: Offline documentation for AI agents to reference without web access (ex: The Model Context Protocol Specs)
- **`source-code-of-dependencies/`**: Read-only references to important related packages for AI agents to reference without web access (ex: `django-rest-framework`)

In all subdirectories below this one, the information that we want to give to CLAUDE and the information we want to give to our human contributors is largely the same. Leverage the CLAUDE.md files you find the same way you would leverage READMEs -- they will contain information on the structure of that directory, commands you might right, organizing principles, etc.

### Development Setup

#### 1. Clone and Install

```bash
git clone https://github.com/zacharypodbela/django-rest-framework-mcp.git
cd django-rest-framework-mcp

# Install the library in development mode with test dependencies
pip install -e ".[dev]"
```

#### 2. Run Tests

All tests are in the `tests/` directory and can be run with pytest:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=djangorestframework_mcp --cov-report=term-missing

# Run specific test file
pytest tests/test_decorators.py

# Run with verbose output
pytest -v
```

#### 3. Manual Testing

Use the demo Django application for manual testing and smoke testing with your own MCP Client.

```bash
# Run the demo application
cd demo
python manage.py migrate # Only need to run the first time you want to run the app.
python manage.py runserver

# The demo app provides:
# - Django Rest Admin interface at http://localhost:8000/
# - Admin interface at http://localhost:8000/admin/
# - MCP tools exposed at http://localhost:8000/mcp/
```

#### 4. Code Quality Tools

This project uses Ruff for linting/formatting and mypy for type checking:

```bash
# Format code (autofix)
ruff format .

# Check linting issues
ruff check .

# Fix auto-fixable linting issues
ruff check --fix .

# Type checking
mypy djangorestframework_mcp

# Run all three and fix any issues before committing
ruff format . && ruff check . && mypy djangorestframework_mcp
```

### New Feature Checklist

If you are developing new features from the roadmap, first ensure you've thought through all of the below questions to ensure your implementation is robust, developer-friendly, and fully integrated with both DRF and MCP requirements.

- How will this functionality be advertised to and usable by LLMs/agents?
- What response will be returned if there are errors?
- What level of customization of the above to we need to offer to developers using our library?
- How can developers override behavior for just MCP requests?

And also ensure you attend to the following required housekeeping items to ensure the codebase stays maintainable:

- Implement tests
  - Unit tests
  - End-to-end tests
  - Regression tests (that ensure normal DRF API based requests continue to work)
- Enhance the Demo application to leverage your new feature and document in the /demo/README.md
- Update any other project documentation if needed, such as this README.md or CLAUDE.md files for any directories you made changes to.
- Format all code, fix any linting issues, and fix any type hints before committing.
