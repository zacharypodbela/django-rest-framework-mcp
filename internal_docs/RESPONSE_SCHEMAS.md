# MCP Response Schemas

This document defines the consistent response schemas used throughout the django-rest-framework-mcp library.

## Response Hierarchy

The library uses a two-level response structure:

1. **JSON-RPC Protocol Level** - Standard JSON-RPC 2.0 responses
2. **MCP Tool Level** - Tool-specific responses within the JSON-RPC result

## JSON-RPC Protocol Level Schemas

### Success Response

```json
{
  "jsonrpc": "2.0",
  "result": <object>, // See MPC Tool Level Schemas below
  "id": <number|string|null>
}
```

**Rules:**

- MUST contain `jsonrpc` field with value `"2.0"`
- MUST contain `result` field with the response data
- MUST contain `id` field which indicates the request we are responding to
- MUST NOT contain `error` field

### Error Response

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": <number>,
    "message": <string>
  },
  "id": <number|string|null>
}
```

**Rules:**

- MUST contain `jsonrpc` field with value `"2.0"`
- MUST contain `error` object with `code` (integer) and `message` (string)
- MUST contain `id` field (null for parse errors, indicates the request we are responding to otherwise)
- MUST NOT contain `result` field

**Standard Error Codes:**

- `-32700`: Parse error
- `-32601`: Method not found
- `-32603`: Internal error

## MCP Tool Level Schemas

Tool responses are contained within the JSON-RPC `result` field.

### call/tool Success Response

```json
{
  "content": [
    {
      "type": "text",
      "text": <stringified_json>
    }
  ]
}
```

**Rules:**

- MUST contain `content` array with at least one item
- Each content item MUST have `type` field set to `"text"`
- Each content item MUST have `text` field containing JSON-serialized tool result
- MUST NOT contain `isError` field

### call/tool Error Response

```json
{
  "content": [
    {
      "type": "text",
      "text": "Error executing tool: <error_message>"
    }
  ],
  "isError": true
}
```

**Rules:**

- MUST contain `content` array with at least one item
- Each content item MUST have `type` field set to `"text"`
- Error text MUST start with `"Error executing tool: "`
- MUST contain `isError` field set to `true`

### initialize Success Response

**Success:**

```json
{
  "protocolVersion": "2025-06-18",
  "capabilities": {
    "tools": {}
  },
  "serverInfo": {
    "name": "django-rest-framework-mcp",
    "version": "0.1.0"
  }
}
```

### tools/list Success Response

```json
{
  "tools": [
    {
      "name": <string>,
      "description": <string>,
      "inputSchema": <json_schema>
    },
    ...
  ]
}
```

## Testing Schema Consistency

The `tests/test_response_schemas.py` file contains comprehensive tests that enforce these schema rules. All responses from the library are validated against these schemas to ensure consistency.

## Examples

### Successful Tool Call

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "customers_list",
    "arguments": {}
  },
  "id": 1
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"id\": 1, \"name\": \"Alice\", \"email\": \"alice@example.com\"}]"
      }
    ]
  },
  "id": 1
}
```

### Failed Tool Call

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "customers_retrieve",
    "arguments": { "kwargs": { "pk": "999999" } }
  },
  "id": 2
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error executing tool: ViewSet returned error: {'detail': 'Not found.'}"
      }
    ],
    "isError": true
  },
  "id": 2
}
```

### Protocol Error (Method Not Found)

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "invalid_method",
  "params": {},
  "id": 3
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32601,
    "message": "Method not found: invalid_method"
  },
  "id": 3
}
```
