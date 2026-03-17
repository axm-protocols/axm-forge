# CLI Reference

## `axm-mcp` — Start the MCP Server

```
axm-mcp
```

Starts the FastMCP server, auto-discovers all installed `axm.tools` entry points, and exposes them as MCP-callable tools.

### Transport Modes

| Mode | How to start | Default port |
|---|---|---|
| **stdio** (default) | `axm-mcp` | — |
| **Streamable HTTP** | `axm-mcp serve` | `9427` (override via `AXM_MCP_PORT`) |

The HTTP transport exposes a `/health` endpoint that returns `{"status": "ok", "tools_count": N}`.

### Built-in Tools

| Tool | Description |
|---|---|
| `list_tools` | List all discovered tools with names and descriptions |
| `verify` | One-shot quality check: audit + init check + AST enrichment |

### MCP Resources

| URI | Description |
|---|---|
| `axm://tools` | JSON catalog of all registered tools (via `read_resource`) |

### Discovered Tools

All tools registered via `axm.tools` entry points are exposed automatically. Common tools include:

| Tool | Package | Description |
|---|---|---|
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 39 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_doi` | `axm-bib` | Resolve DOI → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |
| `bib_extract` | `axm-bib` | Extract text from PDF |

The exact list depends on which packages are installed. Use `list_tools` to see what's available.
