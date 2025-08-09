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
