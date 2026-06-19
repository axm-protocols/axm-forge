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

### Service Management

| Command | Description |
|---|---|
| `axm-mcp install` | Install axm-mcp as a launchd service (macOS) |
| `axm-mcp uninstall` | Remove the launchd service |

`install` locates the `axm-mcp` binary via `find_binary()`, generates a launchd plist from `PLIST_TEMPLATE`, and loads it with `launchctl`. `uninstall` unloads the service and deletes the plist file.

### Built-in Tools

| Tool | Description |
|---|---|
| `verify` | One-shot quality check: audit + init check + AST enrichment |
| `web_fetch` | Fetch web pages with anti-bot bypass (basic / dynamic / stealth) |
| `list_tools` | List all available tools (always enumerates the full surface) |

These built-ins are always registered directly alongside the discovered tools (see `mcp_app.py`).

### Facade Meta-Tools

By default (`AXM_MCP_FACADE=1`) the discovered tools are surfaced through a compact facade instead of being registered one-by-one, keeping the `tools/list` payload small:

| Tool | Description |
|---|---|
| `axm_search` | Search the tool catalog by keyword/tag |
| `axm_describe` | Full invocation contract (typed params + docstring) for one tool |
| `axm_call` | Execute any tool by name and return its text output |
| `axm_capabilities` | List tools grouped by domain |

Set `AXM_MCP_FACADE=0` to register every discovered tool directly instead.

### Discovered Tools

All tools registered via `axm.tools` entry points are discovered automatically and reachable through the facade (`axm_call`) — or registered directly in legacy mode / when they opt into the hot path via `expose_directly`. Common tools include:

| Tool | Package | Description |
|---|---|---|
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 49 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_resolve` | `axm-bib` | Resolve a DOI/arXiv ref → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |
| `bib_extract` | `axm-bib` | Extract text from PDF |

The exact list depends on which packages are installed. Use `list_tools` to see what's available.
