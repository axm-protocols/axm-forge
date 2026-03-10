<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="140" />
</p>

<h1 align="center">axm-mcp</h1>
<p align="center"><strong>MCP server for the AXM ecosystem — runtime tool discovery and execution.</strong></p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-nexus/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm-mcp/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-nexus/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-nexus/gh-pages/badges/axm-mcp/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
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
uv add axm-mcp          # core server
uv add "axm-mcp[all]"   # with all AXM tools
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
| `web_fetch` | built-in | Fetch web pages with anti-bot bypass |
| `axm://tools` | built-in | MCP resource — passive tool catalog |
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 39 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_doi` | `axm-bib` | Resolve DOI → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |
| `bib_extract` | `axm-bib` | Extract text from PDF |

## Learn More

- [Quick Start Tutorial](tutorials/quickstart.md)
- [How to Add a Tool](howto/add-tool.md)
- [How to Verify Setup](howto/verify.md)
- [Architecture](explanation/architecture.md)
- [CLI Reference](reference/cli.md)
