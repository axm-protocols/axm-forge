# CLI Reference

## `axm-mcp` — Start the MCP Server

```
axm-mcp
```

Starts the FastMCP server, auto-discovers all installed `axm.tools` entry points, and exposes them as MCP-callable tools.

### Built-in Tools

| Tool | Description |
|---|---|
| `list_tools` | List all discovered tools with names and descriptions |
| `verify` | One-shot quality check: audit + init check + AST enrichment |

### Discovered Tools

All tools registered via `axm.tools` entry points are exposed automatically. Common tools include:

| Tool | Package | Description |
|---|---|---|
| `ast_describe` | `axm` | Full API surface of a Python package |
| `ast_search` | `axm` | Search functions/classes by name, return type, or base class |
| `ast_impact` | `axm` | Blast radius analysis for a symbol |
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 39 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `search_paper` | `axm-bib` | Search academic papers by title |
| `kind2` | `axm-formal` | Kind 2 model checker for Lustre |

The exact list depends on which packages are installed. Use `list_tools` to see what's available.
