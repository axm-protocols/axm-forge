# AXM MCP Server

> Runtime execution for the AXM protocol ecosystem.

## Overview

`axm-mcp` is the MCP (Model Context Protocol) server that executes AXM protocols. It provides:

- **State Machine** — Formal execution model with validated transitions
- **Session Management** — Persistence, resume, rollback
- **Witnesses** — Validation gates (structural, schema, LLM)
- **Context Catalog** — Task outputs and cross-workflow access

## Installation

```bash
uv pip install axm-mcp
```

## Quick Start

```bash
# Start MCP server
axm-mcp

# Run a protocol
axm run sota-express --topic "AI agent frameworks"
```

## Development

```bash
make install  # Install all dependencies
make check    # Run lint + audit + test
make format   # Auto-format code
```

## Dependencies

- `axm` — Core schemas, loaders, and catalog
- `mcp` — MCP SDK for server implementation
- `loguru` — Logging
- `pydantic` — Runtime validation
