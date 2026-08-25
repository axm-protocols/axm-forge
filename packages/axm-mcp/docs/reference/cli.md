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

### Subcommands

| Command | Flags | Description |
|---|---|---|
| `axm-mcp` (no subcommand) | — | Run in **stdio** mode (backward-compatible default) |
| `axm-mcp serve` | `--host` (default `127.0.0.1`), `--port` (default `9427`) | Start the **Streamable HTTP** server |
| `axm-mcp status` | `--host`, `--port` | Query the running server's `/health` endpoint |
| `axm-mcp stop` | — | Send `SIGTERM` to the running server (identity-verified) |
| `axm-mcp install` | `--port`, `--binary <path>` | Install as a launchd service (macOS) |
| `axm-mcp uninstall` | — | Remove the launchd service |

#### `serve`

Writes a **transactional** PID file (`~/.axm/mcp-server.pid`): it refuses to
start when a live `axm-mcp` server already owns the file, and on exit only
removes the file when it still holds this process's PID — so a failed start
(e.g. a bind conflict) never deletes a healthy server's PID file.

#### `status`

Prints `Server running on HOST:PORT (N tools)` on a healthy `/health`, or
`Server not running` on any transport error (connect refused, read timeout,
malformed body). Exits non-zero when the server is unreachable or replies with
a non-200.

#### `stop`

Reads the PID file, verifies the target process's command line carries the
`axm-mcp` marker (guarding against OS PID reuse), then sends `SIGTERM`. If the
PID is stale or has been reused by an unrelated process, no signal is sent and
the stale PID file is cleaned up.

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Failure — server unreachable (`status`), no/stale/foreign PID (`stop`), refused double `serve`, missing binary or `launchctl` failure (`install`), service not installed (`uninstall`) |

### Environment Variables

| Variable | Default | Effect |
|---|---|---|
| `AXM_MCP_FACADE` | `1` | `1` (or unset) exposes the compact facade; `0`/`false`/`no` registers every discovered tool directly (legacy) |
| `AXM_MCP_PORT` | `9427` | HTTP bind port when `--port` is not passed to `serve` |
| `AXM_DISABLE_TOOLS` | *(empty)* | Comma-separated list of tool **names or glob patterns** excluded at discovery time — e.g. `bib_*,ticket_*,ast_dead_code`. Useful to trim a shared server's surface. Applied in `discover_tools()`; a disabled tool is neither registered nor indexed by the facade |

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
