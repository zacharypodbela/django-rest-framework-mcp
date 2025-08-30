# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is `django-rest-framework-mcp`, a Python library that enables developers to expose Django REST Framework APIs as MCP (Model Context Protocol) servers.

## In This Directory

Refer to @CONTRIBUTING.md for the most important information on how to develop new functionality, which you will be doing a lot. **IMPORTANT:** YOU MUST **ALWAYS** be sure to run the formatter, linter, typechecking, and ensure the full test suite passes (Steps 2 and 4 in that doc) after making a code change!! Do not **ever** say you are done with a task without having done this cleanup.

Refer to `/README.md` for user-facing guide to library.

The repository includes offline documentation in `/external-docs`:

- Django REST Framework API reference
- MCP protocol specification

Full source code of select important dependencies is available in `/source-code-of-dependencies` for deep integration reference. You should never write any code in these files, since this code is not actually running. It's there for you to read and understand:

- `encode-django-rest-framework`: Complete Django REST Framework source code for understanding ViewSet patterns, serializer implementations, request/response handling, etc.

The `/djangorestframework_mcp` directory contains the code for `django-rest-framework-mcp` (the library we're building!).

The `/tests` directory contains all tests (unit and integration). Tests use pytest with Django configuration in conftest.py.

The `/demo` directory is a standalone Django app that can be used to manually test the MCP Server locally.

The `/internal-docs` directory contains lower-level documentation about the implementation, strategy, or goals of the `django-rest-framework-mcp` project. See @internal-docs/CLAUDE.md for full list of resources.
