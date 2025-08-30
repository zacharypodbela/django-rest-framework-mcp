# Contributing

We welcome contributions!

## Project Structure

Unsurprisingly, we're using AI tools pretty actively in our development workflows, and so the project structure has been optimized for collaboration by both humans and agents.

- **`djangorestframework_mcp/`**: The library source code
- **`tests/`**: All tests (unit and integration)
- **`demo/`**: A working Django app for manual testing
- **`/internal-docs`**: Documentation about the implementation, strategy, and/or goals of the `django-rest-framework-api` project.
- **`external-docs/`**: Offline documentation for AI agents to reference without web access (ex: The Model Context Protocol Specs)
- **`source-code-of-dependencies/`**: Read-only references to important related packages for AI agents to reference without web access (ex: `django-rest-framework`)

In all subdirectories below this one, the information that we want to give to CLAUDE and the information we want to give to our human contributors is largely the same. Leverage the CLAUDE.md files you find the same way you would leverage READMEs -- they will contain information on the structure of that directory, commands you might right, organizing principles, etc.

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/zacharypodbela/django-rest-framework-mcp.git
cd django-rest-framework-mcp

# Install the library in development mode with test dependencies
pip install -e ".[dev]"
```

### 2. Run Tests

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

### 3. Manual Testing

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

### 4. Code Quality Tools

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

## New Feature Checklist

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
