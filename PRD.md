# PRD: Django DRF MCP Server Library

### TL;DR

`django-rest-framework-mcp` enables developers to quickly build MCP Servers for their DRF APIs so AI agents and LLM clients can leverage these endpoints as tools. Developers install a package, add decorators to ViewSets or endpoints they want to expose, and clients like Claude Desktop can then call these tools via the Model Context Protocol. The library is open source and follows a strict convention-over-configuration approach, with a long-term goal of DRF feature parity (anything DRF allows clients to do via API — like search, ordering, etc. — LLMs will be able to do through the MCP).

---

## Goals

### Business Goals

- Provide documentation and examples that enable a new developer to integrate in under 15 minutes.

- Start with basics but support progressive enhancement toward full DRF feature parity (pagination, filtering, ordering, versioning, etc.).

### User Goals

- Integrate MCP with an existing DRF project using minimal changes (install & decorate existing code).

- By default reuse existing DRF serializers, permissions, throttling, and filtering logic when called by MCP clients, but remain able to override with custom logic for MCP requests if desired

- Automatically generate rich, self-describing MCP tool schemas, resources, and prompts

- Configure advanced behavior only when necessary; sensible defaults should work out-of-the-box.

### Non-Goals

- Re-implement or replace DRF; this library wraps and maps DRF behavior to MCP, it does not create a parallel framework.

- Build an agent runtime, planning layer, or client UI; we only provide an MCP server compatible with existing clients.

- Support non-DRF frameworks during initial releases (e.g., Flask, FastAPI); initial scope is DRF-only.

---

## User Stories

Personas:

- Django Backend Engineer

- DevOps / Platform Engineer

- Open Source Contributor

Django Backend Engineer

- As a Django engineer, I want to expose my existing ViewSet actions as MCP tools with a decorator, so that AI agents can call my API without custom glue code.

- As a Django engineer, I want tool input/output schemas to be auto-generated from serializers, so that I avoid manual schema maintenance.

- As a Django engineer, I want convention-over-configuration defaults with the ability to override, so that the team moves fast without losing flexibility.

- As a Django engineer, I want a clear path to DRF feature parity, so that we can adopt MCP without blocking on missing functionality.

DevOps / Platform Engineer

- As a platform engineer, I want the MCP server to run within our existing Django app, so that I don’t need to introduce new services or ports.

- As a platform engineer, I want predictable resource usage and logs for MCP requests, so that operations and monitoring are straightforward.

Open Source Contributor

- As an OSS contributor, I want clear extension points and a roadmap, so that I can add support for more DRF features and transports.

---

## First-Time User Experience

Developer journey from zero to calling tools via an MCP client.

- README with quickstart; minimal steps highlighted at the top (install, configure URL, decorate ViewSet).

- Onboarding:

  - Install the package.

  - Add the app to INSTALLED_APPS if required.

  - Add the MCP URL route (default /mcp) into urls.py.

  - Decorate a DRF ViewSet or specific actions to expose as tools.

  - Run the development server and connect an MCP client (e.g., Claude Desktop) to the endpoint.

  - Use provided sample scripts or client guides to verify tools/list and tools/call.

---

## Narrative

Priya maintains a production Django app powered by DRF. Her team has refined serializers, permissions, and filters over years, and now product wants to let an internal AI assistant retrieve and update customer data safely. In the past, Priya would have written a custom integration layer or a new service to bridge the agent to their APIs.

Instead, she installs the Django DRF MCP Server Library. She adds a single URL route for /mcp and decorates her CustomerViewSet. Without changing business logic, the library introspects serializers and actions, exposing list and retrieve as MCP tools. Claude Desktop connects to the /mcp endpoint via MCP, lists available tools with auto-generated schemas, and calls retrieve with the customer_id. The request goes through the same DRF permissions and queryset filters used in production, ensuring consistent behavior and compliance.

As the explore further, Priya's team decides they want limitations on the capabilities of the MCP compared to the human UIs that interact with the APIs. This ensures that the internal AI assistant can only perform actions that are deemed safe and appropriate for its role. The library allows for easy overrides of the default behavior, enabling Priya to customize the MCP's functionality to better align with business requirements and security protocols.

---

## Roadmap

MVP

- Tool Definition Decorator for ModelViewSet / \*APIViewMixin automatically generates tool for all available CRUD actions (list/retrieve/create/update/partial_update/destroy)

- HTTP transport via /mcp endpoint

- Tool discovery and invocation as laid out in [MCP Protocol](https://modelcontextprotocol.io/)

- Input and output schema of tools auto-generated from DRF serializers with primitive types supported (string/int/float/bool/datetime/date/time/UUID)

- Tool execution errors are surfaced to the MCP Client in a way that allows LLM to adjust its behavior and try again

- Test utilities for MCP, similar to APIs where tools can be referenced by "name"

Next

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

Later

- Custom classes - pagination, permission, authentication, etc.

- Object-level permissions (DjangoObjectPermissions)

- Model permissions (DjangoModelPermissions)

- Depth-based serialization support

- Metadata classes (SimpleMetadata)

- Async views/endpoints support

- Streaming responses [Not sure if this is even possible]

- Caching headers support

## New Feature Checklist

This checklist is for open source contributors developing new features from the roadmap. Use it when designing, implementing, or reviewing any new capability to ensure it’s robust, developer-friendly, and fully integrated with both DRF and MCP requirements.

- How will this functionality be advertised to and usable by LLMs/agents?
- What response will be returned if there are errors?
- What level of customization of the above to we need to offer to developers using our library?
- How can developers override behavior for just MCP requests?
- Implement tests (regression tests for normal DRF API based requests in addition to tests for MCP functionality)
- Update project documentation with examples
