<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-mcp — MCP server for the axm-protocols ecosystem</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm-mcp/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm-mcp/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://nexus.axm-protocols.io/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔌 **Auto-discovery** — Finds all `axm.tools` entry points from installed packages
- 🛠️ **MCP bridge** — Exposes discovered tools as Model Context Protocol callables
- ✅ **Verify** — One-shot project quality check: audit + init check + AST enrichment
- 🌐 **Web fetch** — Anti-bot web page fetching via Scrapling (basic / dynamic / stealth)
- 📋 **List tools** — Built-in meta-tool to list all available tools and descriptions
- 📂 **Tool catalog resource** — `axm://tools` MCP resource for passive tool discovery

## Installation

```bash
uv add axm-mcp
```

With all AXM tools:

```bash
uv add "axm-mcp[all]"
```

## Quick Start

```bash
# Start in stdio mode (default — backward-compatible)
axm-mcp

# Start as Streamable HTTP server (default port 9427)
axm-mcp serve

# Check server status
axm-mcp status

# Stop the running server
axm-mcp stop
```

All installed AXM tools are immediately available to any MCP client.

## CLI Commands

| Command | Description |
|---|---|
| `axm-mcp` | Start in **stdio** mode (backward-compatible default) |
| `axm-mcp serve [--host HOST] [--port PORT]` | Start Streamable HTTP server (default port `9427`) |
| `axm-mcp status [--host HOST] [--port PORT]` | Check whether the HTTP server is running |
| `axm-mcp stop` | Send SIGTERM to the running HTTP server |

The HTTP transport exposes a `/health` endpoint returning `{"status": "ok", "tools_count": N}`.
Port can also be set via the `AXM_MCP_PORT` environment variable.

## MCP Tools

| Tool | Package | Description |
|---|---|---|
| `list_tools` | built-in | List all available tools |
| `verify` | built-in | One-shot audit + init check + AST enrichment |
| `web_fetch` | built-in | Fetch web pages with anti-bot bypass (basic / dynamic / stealth) |
| `axm://tools` | built-in | MCP resource — passive tool catalog (via `read_resource`) |
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 39 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_doi` | `axm-bib` | Resolve DOI → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |
| `bib_extract` | `axm-bib` | Extract text from PDF |

## Development

This package is part of the **axm-nexus** workspace.

```bash
git clone https://github.com/axm-protocols/axm-nexus.git
cd axm-nexus
uv sync --all-groups
uv run --package axm-mcp --directory packages/axm-mcp pytest -x -q
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
