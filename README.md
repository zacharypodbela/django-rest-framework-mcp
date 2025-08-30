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

**View lifecycle methods that will be called:**

- **`perform_authentication(request)`** - Called unless `BYPASS_VIEWSET_AUTHENTICATION = True`
- **`check_permissions(request)`** - Called unless `BYPASS_VIEWSET_PERMISSIONS = True`
- **`check_throttles(request)`** - Always called (no bypass option)
- **`determine_version(request, \*args, **kwargs)`\*\* - Always called to set request versioning

**View lifecycle methods that won't be called:**

- **`dispatch(request, args, kwargs)`** - will not be called since we don't use HTTP method+path routing.
- **`initialize_request(request, args, kwargs)`** will not be called. We do create a `rest_framework.requests.Request` from the `django.http.HttpRequest`, but not using this handler.
- **`initial(request, args, kwargs)`** - will not be called.
- **`perform_content_negotiation(request)`** - will not be called since MCP/JSON-RPC dictates the input and output format.
- **`finalize_response(request, response, args, kwargs)`** will not be called.
- **`handle_exception(exc)`** will not be called in the event of an exception\*.

**Additional considerations:**

- The `request` object will be missing API-specific properties like `method`, `path`, or `path_info` since it wasn't created from an actual HTTP API call
- Content negotiation is bypassed since MCP always uses JSON

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

### Authentication

On the subject of Authentication, the Model Context Protocol states:

1. Implementations using an HTTP-based transport SHOULD conform to the OAuth specification detailed [here](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization#authorization-flow).
2. Implementations using an STDIO transport SHOULD NOT follow the above specification, and instead retrieve credentials from the environment.
3. Additionally, clients and servers MAY negotiate their own custom authentication and authorization strategies.

Our library enables you to leverage DRF's authentication framework on both the MCP endpoint level and individual ViewSet level, giving you flexibility in how you secure your MCP tools.

#### Using Existing API Authentication on ViewSets

If your ViewSet specifies `authentication_classes` and/or `permission_classes`, MCP client requests will be required to authenticate and pass permission checks using the same methods as your normal API requests:

```python
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

@mcp_viewset()
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
```

MCP clients then authenticate via standard HTTP headers:

```bash
# HTTP headers
POST /mcp/ HTTP/1.1
Authorization: Token your-token-here

# HTTP body
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_customers",
    "arguments": {}
  },
  "id": 1
}
```

#### Defining Authentication and Permissions on the MCP Endpoint

You can add authentication to requests made to the `/mcp` endpoint by subclassing `MCPView` and setting the `authentication_classes` property, just as you would for an `APIView`. You can add permissions to requests made to the `/mcp` endpoint by overriding and implementing the `has_mcp_permission` method. (The default implementation of `has_mcp_permission()` returns `True`, allowing all requests.)

```python
from djangorestframework_mcp.views import MCPView
from rest_framework.authentication import TokenAuthentication

class AuthenticatedMCPView(MCPView):
    authentication_classes = [TokenAuthentication]

    def has_mcp_permission(self, request):
        """Override this method to implement custom permission logic."""
        return request.user.is_authenticated

# Then in urls.py
urlpatterns = [
    path('mcp/', AuthenticatedMCPView.as_view()),
]
```

The `has_mcp_permission(self, request)` method is called after authentication, so `user` and `auth` will be both set allowing you to implement any custom authorization logic:

```python
class RestrictedMCPView(MCPView):
    authentication_classes = [TokenAuthentication]

    def has_mcp_permission(self, request):
        # Only allow users in the 'mcp_users' group
        return (
            request.user.is_authenticated
            and request.user.groups.filter(name='mcp_users').exists()
        )
```

Just as with DRF, if you have authentication classes but no permission requirements, unauthenticated requests are allowed to continue and `request.user` will be an `AnonymousUser`.

#### Bypassing ViewSet Authentication

In cases where you want to apply different authentication methods and/or permissions rules for MCP clients versus regular API clients, you can bypass ViewSet-level authentication and/or permissions:

```python
# settings.py
DJANGORESTFRAMEWORK_MCP = {
    'BYPASS_VIEWSET_AUTHENTICATION': True,  # Skip authentication on ViewSets
    'BYPASS_VIEWSET_PERMISSIONS': True,     # Skip permissions on ViewSets
}
```

#### Authenticating STDIO Transport (Using MCP-Remote)

When using STDIO transport through MCP-Remote, authentication credentials to be passed as HTTP headers can be set as environment variables like this:

```json
{
  "mcpServers": {
    "my-django-mcp": {
      "command": "node",
      "args": [
        "path/to/mcp-remote",
        "http://localhost:8000/mcp/",
        "--transport",
        "http-only",
        "--header",
        "Authorization:${AUTH_HEADER}" // Some setups don't escape whitespaces of args, so we recommend setting the entire header as an env var
      ],
      "env": {
        "AUTH_HEADER": "your-header-here"
      }
    }
  }
}
```

#### Authentication Error Handling

When authentication fails, the default behavior is for the library to return proper HTTP status codes (401/403) and WWW-Authenticate headers in compliance with both HTTP and MCP specifications. The JSON-RPC response body also includes this information in the `error.data` field and human readable error message to guide LLMs.

Example response:

```json
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Token
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Authentication credentials were not provided.",
    "data": {
      "status_code": 401,
      "www_authenticate": "Token"
    }
  },
  "id": 1
}
```

While the MCP protocol specification clearly states that HTTP 401/403 status codes should be returned for authentication and permission errors, many MCP clients don't properly conform to this specification and are unable to handle these cases. (For example, MCP's own Typescript SDK doesn't currently handle 403 errors. See this [Github Issue](https://github.com/modelcontextprotocol/typescript-sdk/issues/541).) To better support compatibility with a wide variety of clients while the community and standards continue to evolve, you can enable the `RETURN_200_FOR_ERRORS` to return HTTP 200 status codes even for authentication/permission failures. This setting only affects the HTTP status code returned - the JSON-RPC error format remains the same, ensuring LLMs can still understand and react to failures.

```python
# settings.py
DJANGORESTFRAMEWORK_MCP = {
    'RETURN_200_FOR_ERRORS': True,  # Default: False
}
```

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

        # NOTE: The is_mcp_request property is only set for MCP calls, so trying to access it directly will result in an AttributeError if the Request did not originate from an MCP request. The simplest solution is to access the value with getattr instead.
        is_mcp_request = getattr(request, 'is_mcp_request', False)

        # Limit MCP clients to active customers only
        if is_mcp_request:
            queryset = queryset.filter(is_active=True)

        return queryset
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

### Authentication in Tests

`MCPClient` inherits from Django's `django.test.Client`, so all normal helper methods for authentication like `login()`, `force_login()`, and setting default headers are available to authenticate your MCP calls.

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
- ✅ Authentication

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

- Advertising custom headers, kwargs to MCP Clients

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

### Views

#### `MCPView`

The main MCP HTTP endpoint handler that processes JSON-RPC requests and routes them to appropriate ViewSets.

**Properties:**

- `authentication_classes` (list[Type[BaseAuthentication]]): List of authentication classes to use for the MCP endpoint. Defaults to empty list (no authentication required).

**Methods:**

- `has_mcp_permission(self, request: HttpRequest) -> bool`: Override this method to implement custom permission logic for the MCP endpoint. Called after authentication, so `request.user` and `request.auth` are available. Default behavior returns True (allows all requests).

### Settings

#### `mcp_settings`

Global settings object for accessing django-rest-framework-mcp configuration. Import from `djangorestframework_mcp.settings`.

**Properties (Available Settings):**

- `BYPASS_VIEWSET_AUTHENTICATION` (bool, default: False): When True, skips authentication checks configured on ViewSets during MCP tool execution.
- `BYPASS_VIEWSET_PERMISSIONS` (bool, default: False): When True, skips permission checks configured on ViewSets during MCP tool execution.
- `RETURN_200_FOR_ERRORS` (bool, default: False): When True, returns HTTP 200 status codes for authentication and permission errors while preserving JSON-RPC error information. This improves compatibility with MCP clients that don't properly handle HTTP error status codes. When False, returns proper HTTP status codes (401/403) in compliance with HTTP and MCP specifications.

### Extended Request Properties

**NOTE:** These properties are only set for MCP calls, so trying to access them directly will result in an `AttributeError` if the `Request` did not originate from an MCP request. The simplest solution is to access them with `getattr` instead.

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
