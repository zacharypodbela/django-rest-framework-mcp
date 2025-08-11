# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is `django-rest-framework-mcp`, a Python library that enables developers to expose Django REST Framework APIs as MCP (Model Context Protocol) servers.

## In This Directory

The repository includes offline documentation in `/external-docs`:

- Django REST Framework API reference
- MCP protocol specification

Full source code of select important dependencies is available in `/source-code-of-dependencies` for deep integration reference. You should never write any code in these files, since this code is not actually running. It's there for you to read and understand:

- `encode-django-rest-framework`: Complete Django REST Framework source code for understanding ViewSet patterns, serializer implementations, request/response handling, etc.

The `/djangorestframework_mcp` directory contains the code for `django-rest-framework-mcp` (the library we're building!).

The `/tests` directory contains all tests (unit and integration). Tests use pytest with Django configuration in conftest.py.

The `/demo` directory is a standalone Django app that can be used to manually test the MCP Server locally.

The `/internal-docs` directory contains lower-level documentation about the implementation, strategy, or goals of the `django-rest-framework-mcp` project. See @internal-docs/CLAUDE.md for full list of resources.

Refer to @README.md for user-facing guide to library. Be sure to pay close attention to the "Contributing" section which contains commands for running tests and a new feature checklist of things you must always do when developing new functionality. You are a contributor after all!
