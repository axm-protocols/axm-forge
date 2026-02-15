<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-init/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-mcp — MCP server for the axm-protocols ecosystem</strong>
</p>


<p align="center">
  <a href="https://github.com/axm-protocols/axm-mcp/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://axm-protocols.github.io/axm-mcp/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-mcp/gh-pages/badges/axm-init.json" alt="axm-init"></a>
  <a href="https://github.com/axm-protocols/axm-mcp/actions/workflows/axm-audit.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-mcp/gh-pages/badges/axm-audit.json" alt="axm-audit"></a>
  <a href="https://coveralls.io/github/axm-protocols/axm-mcp?branch=main"><img src="https://coveralls.io/repos/github/axm-protocols/axm-mcp/badge.svg?branch=main" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://axm-protocols.github.io/axm-mcp/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔌 **Auto-discovery** — Finds all `axm.tools` entry points from installed packages
- 🛠️ **MCP bridge** — Exposes discovered tools as Model Context Protocol callables
- ✅ **Verify** — One-shot project quality check: audit + init check + AST enrichment
- 📋 **List tools** — Built-in meta-tool to list all available tools and descriptions

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
# Start the MCP server
axm-mcp
```

All installed AXM tools are immediately available to any MCP client.

## MCP Tools

| Tool | Package | Description |
|---|---|---|
| `list_tools` | built-in | List all available tools |
| `verify` | built-in | One-shot audit + init check + AST enrichment |
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 39 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_doi` | `axm-bib` | Resolve DOI → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |

## Development

```bash
git clone https://github.com/axm-protocols/axm-mcp.git
cd axm-mcp
uv sync --all-groups
uv run pytest           # 68 tests
uv run ruff check src/  # lint
```

## License

Apache License 2.0
