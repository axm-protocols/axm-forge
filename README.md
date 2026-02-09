# AXM MCP Server

> Runtime execution for the AXM protocol ecosystem.

## Installation

```bash
uv pip install -e .
```

## Development

```bash
uv sync --group dev
uv run pytest
uv run mypy src/
uv run ruff check src/
```  

## Dependencies

- `axm` — Core schemas, loaders, and catalog
- `mcp` — MCP SDK for server implementation
- `loguru` — Logging
- `pydantic` — Runtime validation
