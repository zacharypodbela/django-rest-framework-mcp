# Q: Why are we not using the python-sdk MCP package to build our MCP server?

## Current Implementation (Manual JSON-RPC)

**What we're doing:**

- Manual JSON-RPC parsing in `MCPView.post()`
- Manual protocol handling (`initialize`, `tools/list`, `tools/call`)
- Manual error response formatting
- Custom tool execution logic
- \~160 lines of protocol implementation

## MCP Python SDK Approach

**What the SDK provides:**

- `FastMCP` class handles all JSON-RPC protocol details
- Built-in `tools/list`, `tools/call`, `initialize` handling
- Automatic schema generation from function signatures
- Built-in error handling and response formatting
- ASGI/HTTP transport layers included

## Analysis

**Pro: Yes, using the SDK would reduce re-implementation**

### 1. Protocol Layer (\~80 lines saved):

- No manual JSON-RPC parsing
- No manual `initialize` / `tools/list` / `tools/call` handlers
- Automatic error response formatting

### 2. Schema Generation (\~50+ lines in `schema.py` could be simplified):

- SDK auto-generates schemas from function signatures
- Current DRF-to-JSON-Schema conversion could be replaced

### 3. Transport Layer:

- Built-in HTTP handling via `StreamableHTTPSessionManager`
- Current Django view → could become a simple adapter

## 🚧 BUT, Con: Doing so would greatly increase Django integration complexity

### 1. The deleted `server.py` was attempting this approach:

- Used `FastMCP` + `StreamableHTTPSessionManager`
- Required complex ASGI ↔ Django adapters (`_call_starlette_handler`)
- Became more complex than manual implementation

### 2. Core Challenge – ViewSet Integration:

- SDK expects functions like `async def my_tool(param1: str):`
- We need to bridge: **SDK Tool Function → DRF ViewSet.action**
- Current `MCPToolExecutor` would still be needed

### 3. Django-specific Features:

- Request context (`request.is_mcp_request`)
- DRF permissions, authentication, throttling
- Django's native HTTP handling vs ASGI

## Final Answer

The SDK could reduce **\~30–40% of code** (protocol handling),
but the **core complexity would remain** (DRF integration).

The current approach is actually quite elegant because:

1. **Simple & Django-native** – Uses Django views directly
2. **No impedance mismatch** – No ASGI ↔ Django conversion needed
3. **Full DRF integration** – Easy to add permissions, auth, etc.
4. **Debuggable** – Standard Django request/response cycle

> The SDK approach was actually tried (the deleted `server.py`) but abandoned because the Django integration complexity outweighed the protocol simplification benefits.

# Q: Why do we require developers to pass in an input serializer classes for custom actions?

## The Problem We Encountered

We initially tried to generalize schema generation by automatically detecting body input needed by the endpoint by inspecting serializer fields for writeable (non-read-only) fields. However, this approach failed because business logic determines data requirements, not serializer definitions.

A custom action might need completely different fields than what's in the ViewSet's main serializer:

```python
@action(detail=False, methods=['post'])
def generate(self, request):
    user_prompt = request.data['user_prompt']
    llm_response = call_llm(user_prompt)
    return Response({'llm_response': llm_response})
```

Even for CRUD endpoints, the relationship between serializers and actual data usage is loose - A ViewSet might override the default implementation of a CRUD action to use something different than what's in the serializer:

```python
def create(self, request, *args, **kwargs):
    if request.data.get('send_email_on_create'):
        send_email()

    return super().create(request, *args, **kwargs)
```

## Our Architectural Decision

We decided to extend the existing @mcp_tool decorator to accept a serializer parameter that lets developers explicitly declare input requirements. It is required for custom actions and optional for default CRUD actions. This approach makes sense because:

- Integrates cleanly with existing decorator architecture
- Only the developer knows what their business logic actually needs - we can't guess it from static analysis of serializer definitions alone.
- We need a full Serializer class as opposed to just a dictionary representing the schema b/c the dictionaries don't provide enough context to fill out the description, format, etc. which is essential for good LLM performance.

# Q: Why do MCP tool input schemas have top-level keys like 'body' and 'kwargs'?

## The Problem: Multiple Input Sources in DRF ViewSets

Django REST Framework ViewSet actions can receive data from multiple sources:

- **Request body** (`request.data`) - JSON payload data
- **URL path parameters** (`kwargs`) - Like `pk` for detail views, `lookup_field` values
- **Query parameters** (`request.query_params`) - URL query string parameters [future]
- **Headers** (`request.headers`) - HTTP headers [future]

Each source serves a different purpose and gets passed to ViewSet methods differently.

## Our Architectural Decision: Explicit Top-Level Keys

We structured MCP tool input schemas with explicit top-level keys that map directly to these input sources:

```json
{
  "body": {
    "customer_name": "John Doe",
    "email": "john@example.com"
  },
  "kwargs": {
    "pk": "123"
  }
}
```

**Key Mapping:**

- `body` → `request.data` (request body/payload)
- `kwargs` → direct parameters to ViewSet action methods
- `query_params` → `request.query_params` [planned future feature]
- `headers` → `request.headers` [planned future feature]

## Why This Design?

**Simplicity.** Each input source can have its own logic for generating schemas, and when a request comes in it's dead simple to unpack the values and pass them to ViewSets correctly.

With explicit top-level keys, the request handling becomes straightforward:

```python
# Clean unpacking
body_data = mcp_request.get('body', {})
kwargs_data = mcp_request.get('kwargs', {})

# Direct assignment
request.data = body_data
viewset_action(request, **kwargs_data)
```

## Alternative Considered: Flat Schema

We considered a flat schema where all parameters are at the top level:

```json
{
  "customer_name": "John Doe", // body
  "email": "john@example.com", // body
  "pk": "123" // kwargs
}
```

**Rejected because:**

- Have to leverage the functions that generated the schema to understand which parameters go where
- Parameter name conflicts between sources
- Less maintainable as input sources grow
