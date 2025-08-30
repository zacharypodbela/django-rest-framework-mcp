## Setup

The first time you clone this repo, you'll need to do a few additional steps to set things up.

1. Run migrations

```bash
python manage.py migrate
```

2. (Optional) Create at admin user

Admin users allow you to log into and leverage Django's Admin interface to easily create and modify data in the database, which can be useful for setting up testing scenarios and debugging.

```bash
python manage.py createsuperuser  # Creates admin user
```

3. (Optional) Generate instructions on how to authenticate from your MCP Client

NOTE: If you want to test Token based authentication this step is required.

```bash
# Then set up MCP authentication for that user
python manage.py setup_test_auth testuser testpass123
```

This command will:

- Find an existing user or create a new one with the specified credentials
- Generate an auth token for the user
- Display comprehensive test instructions including curl examples

## Run the App

```bash
# Run the demo application
cd demo
python manage.py runserver

# The demo app provides:
# - Django Rest Admin interface at http://localhost:8000/
# - Admin interface at http://localhost:8000/admin/
# - MCP tools exposed at http://localhost:8000/mcp/
```

### Disabling Authentication

If you want to test without authentication, simply comment out the `DEFAULT_PERMISSION_CLASSES` in `demo/settings.py`:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [...],
    # "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

## Demo Features

| Feature Name                                  | File                                                | Example Description                                                                                                                                                                |
| --------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Basic CRUD Actions**                        | `blog/views.py:12-66`                               | `PostViewSet` demonstrates all CRUD actions (list, retrieve, create, update, partial_update, destroy) exposed as MCP tools                                                         |
| **Custom Input Serializers for CRUD Actions** | `blog/views.py:22-37`                               | The `create` action uses `CreatePostSerializer` with additional fields beyond the model                                                                                            |
| **MCP-Specific Behavior**                     | `blog/views.py:30-32`                               | Posts created via MCP automatically get "Created via MCP" footer using `request.is_mcp_request`                                                                                    |
| **Custom Actions (No Input)**                 | `blog/views.py:39-50`                               | `reverse` action demonstrates custom actions with `input_serializer=None`                                                                                                          |
| **Custom Actions (With Input)**               | `blog/views.py:52-62`                               | `bulk_create` action demonstrates custom actions with input validation                                                                                                             |
| **Custom Detail Action**                      | `blog/views.py:39-50`                               | `reverse` action demonstrates how custom actions on a detail endpoint automatically require a `lookup_field` `kwarg` from MCP Clients                                              |
| **ListSerializers**.                          | `blog/serializers.py:20-21`                         | `BulkPostSerializer` showcases accepting arrays of objects as input                                                                                                                |
| **Custom Tool Metadata**                      | `blog/views.py:23-27`, `40-42`, `54-58`             | Multiple examples of custom `name`, `title`, and `description` for MCP tools                                                                                                       |
| **Selective Action Registration**             | `blog/views.py:68-71`                               | `CustomerViewSet` only exposes `['list', 'retrieve', 'deactivate']` actions as MCP tools, not full CRUD                                                                            |
| **Custom Basename**                           | `blog/views.py:69`                                  | Uses `basename='customer_mgmt'` to end up with tool names like `customer_mgmt_list` instead of `customers_list`                                                                    |
| **Primitive Field Types**                     | `blog/models.py:14-56`, `blog/serializers.py:24-85` | Customer model demonstrates CharField, EmailField, DecimalField, IntegerField, FloatField, BooleanField, DateField, TimeField, UUIDField                                           |
| **Field Constraints**                         | `blog/models.py:16-53`, `blog/serializers.py:25-81` | Shows Min/max length, min/max values are advertised in input schema so that MCP client can comply                                                                                  |
| **Help Text and Labels**                      | `blog/models.py:19`, `blog/serializers.py:28-29`    | All fields include descriptive `help_text` and `label` to pass additional context to MCP client                                                                                    |
| **Nested Serializers**                        | `blog/serializers.py:87-184`                        | `OrderSerializer` accepts nested `OrderItemSerializer` objects in single create request                                                                                            |
| **Required vs Optional Fields**               | `blog/serializers.py:120-142`                       | Info on Required fields (`customer_name`, `items`) vs optional fields (`notes`) is passed to MCP Client                                                                            |
| **ViewSet Defined Authentication**            | `demo/settings.py:129-139`                          | All ViewSets require authentication via Token, Session, or Basic auth - demonstrates how MCP can leverage existing API authentication                                              |
| **ViewSet Defined Permissions**               | `demo/views.py:78`                                  | The Customer Management ViewSet is only available to admins. This properly applies to both MCP and API Requests, even if using a different authentication method for MCP requests. |
