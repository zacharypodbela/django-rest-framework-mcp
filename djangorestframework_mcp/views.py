"""MCP HTTP endpoint views."""

import json
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework.parsers import JSONParser
from rest_framework.request import Request

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
                result = self.handle_initialize()
            elif method == "notifications/initialized":
                # Sent by the client to acknowledge the receipt of our response to its initialize handshake
                # No response is expected
                return HttpResponse(status=204)  # No Content
            elif method == "tools/list":
                result = self.handle_tools_list()
            elif method == "tools/call":
                result = self.handle_tools_call(params)
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

    def handle_initialize(self) -> Dict[str, Any]:
        """Handle initialize request."""
        # The only capabilities we currently support are tool calling (without listChanged notifications)
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "django-rest-framework-mcp", "version": "0.1.0a2"},
        }

    def handle_tools_list(self) -> Dict[str, Any]:
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

    def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
            result = self.execute_tool(tool, tool_params)

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

    def execute_tool(self, tool: MCPTool, params: Dict[str, Any]) -> Any:
        """Execute a tool using the structured kwargs+body parameter format.

        This method manually calls DRF lifecycle methods to ensure proper
        request handling while avoiding HTTP method semantics since MCP is RPC-based.
        """
        viewset_class = tool.viewset_class
        action = tool.action

        # Create ViewSet instance
        viewset = viewset_class()

        # Extract structured parameters
        method_kwargs = params.get("kwargs", {})
        body_data = params.get("body", {})

        # Create a new HttpRequest that represents the equivalent API call
        body_bytes = json.dumps(body_data).encode("utf-8") if body_data else b"{}"
        request = HttpRequest()
        request.META = {
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(body_bytes)),
        }
        request._body = body_bytes
        request._read_started = True  # We aren't creating a proper stream. Marking it as started tells the parser it does not need to read it as a stream.

        # Replicate what `rest_framework.views.APIView.dispatch` does during a normal API Request, but specialized for MCP.

        # Step 1: Initialize request - converts HttpRequest to DRF Request
        # Based on the implementation of `rest_framework.views.APIView.initialize_request`
        # but without parsers or content negotiation since those don't apply to MCP Request:
        drf_request = Request(
            request,
            parsers=[JSONParser()],  # MCP always uses JSON
            authenticators=viewset.get_authenticators(),
        )
        # From `rest_framework.viewsets.ViewSetMixin.initialize_request`:
        viewset.action = action

        # Mark request as coming from MCP
        drf_request.is_mcp_request = True

        # Step 2: Set up ViewSet context
        viewset.args = ()
        viewset.kwargs = method_kwargs.copy()
        viewset.headers = {}  # In the future, this will be passed in via a headers param.
        viewset.request = drf_request

        # Step 3: Call `initial` to do authentication, permissions, throttling
        viewset.initial(drf_request, *viewset.args, **viewset.kwargs)

        # Step 4: Get and call the action method directly
        if not hasattr(viewset, action):
            raise ValueError(f"ViewSet does not support action: {action}")

        action_method = getattr(viewset, action)
        response = action_method(drf_request, **method_kwargs)

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
