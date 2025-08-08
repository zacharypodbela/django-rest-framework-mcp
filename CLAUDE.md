# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is `django-rest-framework-mcp`, a Python library that enables developers to expose Django REST Framework APIs as MCP (Model Context Protocol) servers.

## In This Directory

The repository includes offline documentation in `/external-docs`:

- Django REST Framework API reference
- MCP protocol specification

Full source code of select important dependencies is available in `/source-code-of-dependencies` for deep integration reference. You should never write any code in these files, since this code is not actually running. It's there for you to read and understand.

Refer to `/PRD.md` for complete product requirements including:

- Goals
- User Stories
- First-Time User Experience
- Narrative
- Roadmap
- New Feature Checklist

The `/src` directory contains the actual `django-rest-framework-mcp` library code.

The `/demo` directory contains a basic Django DRF app that can be run with `python manage.py runserver` and serves as the location for end-to-end tests.

# New Feature Checklist

The New Feature Checklist from the PRD is so important, I'm copying it here. For every feature we must consider / do the following:

- How will this functionality be advertised to and usable by LLMs/agents?
- What response will be returned if there are errors?
- What level of customization of the above to we need to offer to developers using our library?
- How can developers override behavior for just MCP requests?
- Implement tests (regression tests for normal DRF API based requests in addition to tests for MCP functionality)
- Update project documentation with examples
