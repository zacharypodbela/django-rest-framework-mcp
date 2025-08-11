"""MCP HTTP endpoint views."""

import json
from typing import Any, Dict, Optional

from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .registry import registry
from .schema import generate_tool_schema
from .types import MCPTool


@method_decorator(csrf_exempt, name="dispatch")
class MCPView(View):
    """Main MCP HTTP endpoint handler."""

    def post(self, request):
        """Handle MCP requests."""
        try:
            # Parse the JSON-RPC request
            body = json.loads(request.body)

            # Extract the method and params
            method = body.get("method")
            params = body.get("params", {})
            request_id = body.get("id")

            # Mark this as an MCP request
            request.is_mcp_request = True

            # Route to appropriate handler
            if method == "initialize":
                result = self.handle_initialize(params)
            elif method == "notifications/initialized":
                # Sent by the client to acknowledge the receipt of our response to its initialize handshake
                # No response is expected
                return HttpResponse(status=204)  # No Content
            elif method == "tools/list":
                result = self.handle_tools_list(params)
            elif method == "tools/call":
                result = self.handle_tools_call(request, params)
            else:
                # Method not found
                return self.error_response(
                    request_id, -32601, f"Method not found: {method}"
                )

            # Return JSON-RPC response
            return JsonResponse({"jsonrpc": "2.0", "result": result, "id": request_id})

        except json.JSONDecodeError:
            return self.error_response(None, -32700, "Parse error")
        except Exception as e:
            return self.error_response(
                body.get("id") if "body" in locals() else None,
                -32603,
                f"Internal error: {str(e)}",
            )

    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        # The only capabilities we currently support are tool calling (without listChanged notifications)
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "django-rest-framework-mcp", "version": "0.1.0"},
        }

    def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/list request."""
        tools = []

        for tool in registry.get_all_tools():
            tool_schema = generate_tool_schema(tool)

            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool_schema["inputSchema"],
            }

            # Add title if present
            if tool.title:
                tool_dict["title"] = tool.title

            tools.append(tool_dict)

        return {"tools": tools}

    def handle_tools_call(self, request, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        tool_params = params.get("arguments", {})

        try:
            # Find the tool
            if not tool_name:
                raise Exception("Tool name is required")
            tool = registry.get_tool_by_name(tool_name)
            if not tool:
                # This should be handled as a protocol-level error, not a tool execution error
                raise Exception(f"Tool not found: {tool_name}")

            # Execute the tool
            result = self.execute_tool(request, tool, tool_params)

            # Per latest MCP specification (2025-06-18), JSON should be returned in both
            # structured content and as stringified text content (the latter for backwards compatibility)
            response = {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}]
            }
            # Add structured content if result is JSON-serializable
            try:
                # Test if result can be JSON serialized (for structuredContent validation)
                json.dumps(result)
                response["structuredContent"] = result
            except (TypeError, ValueError):
                # If result contains non-JSON-serializable data, skip structuredContent
                # The text content will still contain the string representation
                pass

            return response

        except Exception as e:
            return {
                "content": [
                    {"type": "text", "text": f"Error executing tool: {str(e)}"}
                ],
                "isError": True,
            }

    def error_response(
        self, request_id: Optional[Any], code: int, message: str
    ) -> JsonResponse:
        """Create a JSON-RPC error response."""
        return JsonResponse(
            {
                "jsonrpc": "2.0",
                "error": {"code": code, "message": message},
                "id": request_id,
            }
        )

    def execute_tool(self, request, tool: MCPTool, params: Dict[str, Any]) -> Any:
        """Execute a tool using the structured kwargs+body parameter format."""
        viewset_class = tool.viewset_class
        action = tool.action

        # Create ViewSet instance with proper DRF setup
        viewset = viewset_class()

        # Set up the request context properly
        viewset.request = request
        viewset.action = action
        viewset.format_kwarg = None
        viewset.args = ()

        # Mark request as coming from MCP
        request.is_mcp_request = True

        # Extract structured parameters
        method_kwargs = params.get("kwargs", {})
        body_data = params.get("body", {})

        # Set up ViewSet kwargs from method_kwargs
        viewset.kwargs = method_kwargs.copy()

        # Set up request data from body
        request.data = body_data

        # Get the method dynamically and call it
        if not hasattr(viewset, action):
            raise ValueError(f"ViewSet does not support action: {action}")

        action_method = getattr(viewset, action)
        response = action_method(request, **method_kwargs)

        # Handle DRF Response objects
        if hasattr(response, "data"):
            # Handle DRF error responses
            if response.status_code >= 400:
                raise ValueError(f"ViewSet returned error: {response.data}")

            # Handle successful responses
            if response.data is not None:
                return response.data
            else:
                # For responses like 204 No Content (destroy), return a success message
                return {"message": "Operation completed successfully"}

        return response
