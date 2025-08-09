# Django REST Framework MCP

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
    path('', include('djangorestframework_mcp.urls')),
]
```

4. Transform any DRF ViewSet into MCP tools with a single decorator:

```python
from djangorestframework_mcp import mcp_tool

@mcp_tool()
class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
```

With that one line of code all CRUD actions of your ViewSet are exposed as MCP tools:

- List customers with `customers_list`
- Retrieve a customer with `customers_retrieve`
- Create new customers with `customers_create`
- Update customers with `customers_update`
- Delete customers with `customers_destroy`

The library automatically:

- Generates tool schemas from your DRF serializers
- Preserves your existing permissions, authentication, and filtering
- Provides helpful error messages to guide LLMs

5. Connect any MCP client to `http://localhost:8000/mcp/` and try it out!

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

## Advanced Configuration

### Custom Tool Names and Descriptions

Override the default tool names to help LLMs understand your tools better:

```python
@mcp_tool(name="customer_management")
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    @mcp_tool.action(
        name="get_customer",
        description="Retrieve a specific customer by their ID"
    )
    def retrieve(self, request, pk=None):
        return super().retrieve(request, pk)
```

### MCP-Specific Overrides

Sometimes you want different behavior for MCP requests vs regular API requests. You have two options for achieving this.

#### Option 1: Inheritance (Recommended)

Create a dedicated ViewSet for MCP that inherits from your existing ViewSet.

```python
@mcp_tool()
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
@mcp_tool()
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
from djangorestframework_mcp.test import MCPTestCase

class CustomerMCPTests(MCPTestCase):
    def test_list_customers(self):
        # Create test data
        Customer.objects.create(name="Alice", email="alice@example.com")
        Customer.objects.create(name="Bob", email="bob@example.com")

        # Call the MCP tool
        result = self.call_tool("customers_list")

        # Assert the response
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 2)
```

## Roadmap

### Currently Supported DRF Features

**MVP Features (Available Now)**

- ✅ Automatic tool generation for ModelViewSet / APIViewMixins CRUD actions (list/retrieve/create/update/partial_update/destroy)
- ✅ HTTP transport via `/mcp` endpoint
- ✅ Full MCP protocol support (tool discovery and invocation) as laid out in [MCP Protocol](https://modelcontextprotocol.io/)
- ✅ Auto-generated tool input/output schemas from DRF serializers
- ✅ Primitive type support (string/int/float/bool/datetime/date/time/UUID)
- ✅ Test utilities for MCP tools

### Future Roadmap

- Resource and prompt discovery and invocation as laid out in [MCP Protocol](https://modelcontextprotocol.io/)

- Browsable UI of MCP tool, resource, and prompts discovery and invocation

- Tool Definition Decorator for any subclass of ViewSet/GenericViewSet [Not sure if we'll support both - TBD]

- Tool Definition Decorator and automatic detection for custom actions defined via @action (detail or list)

- Required/optional inferred automatically

- Constraints (min/max length, min/max value) inferred automatically

- Decorate custom validators with instructions (which will be shared with the MCP Client)

- Relationship fields (PK/Slug/StringRelated)

- Support for Nested serializers

- Arrays/objects/JSONB fields

- Enum fields

- help_text/label passed back to MCP Client as parameter descriptions

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

#### `@mcp_tool(name=None)`

Decorator for ViewSets to expose as MCP tools.

**Parameters:**

- `name` (str, optional): Custom name for the tool set. Defaults to the ViewSet's model name.

#### `@mcp_tool.action(name=None, description=None)`

Decorator for individual ViewSet actions to customize their MCP exposure.

**Parameters:**

- `name` (str, optional): Custom name for this specific action.
- `description` (str, optional): Description for this specific action.

### Extended HttpRequest Properties

#### `.is_mcp_request`

Check if the current request is coming from an MCP client.

### Test Utilities

#### `MCPTestCase`

Base test case class for testing MCP tools. Provides methods that mimic an MCP Client.

**Methods:**

- `call_tool(tool_name, params=None)`: Call an MCP tool and return the result
- `list_tools()`: List all available MCP tools

## Contributing

We welcome contributions!

### Project Structure

Unsurprisingly, we're using AI tools pretty actively in our development workflows, and so the project structure has been optimized for collaboration by both humans and agents.

- **`src/`**: The actual `django-rest-framework-mcp` framework source code
- **`test-app/`**: A working Django app for manual testing and end-to-end testing
- **`external-docs/`**: Offline documentation for AI agents to reference without web access (ex: The Model Context Protocol Specs)
- **`source-code-of-dependencies/`**: Read-only references to important related packages for AI agents to reference without web access (ex: `django-rest-framework`)

### Development Setup

**TBD**

### New Feature Checklist

If you are developing new features from the roadmap, ensure you've thought through all of the below to ensure it’s robust, developer-friendly, and fully integrated with both DRF and MCP requirements.

- How will this functionality be advertised to and usable by LLMs/agents?
- What response will be returned if there are errors?
- What level of customization of the above to we need to offer to developers using our library?
- How can developers override behavior for just MCP requests?
- Implement tests (regression tests for normal DRF API based requests in addition to tests for MCP functionality)
- Update project documentation, especially this README and any CLAUDE.md files
