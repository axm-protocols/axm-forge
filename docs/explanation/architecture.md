# Architecture

## Overview

`axm-mcp` is a thin MCP shell with zero imports from AXM core. It discovers tools at runtime via Python entry points and exposes them over the Model Context Protocol. Two transport modes are supported: **stdio** (legacy, one process per conversation) and **Streamable HTTP** (recommended, single shared server).

```mermaid
graph TD
    subgraph "MCP Layer"
        Server["FastMCP Server"]
        ListTools["list_tools()"]
        Verify["verify()"]
        WebFetch["web_fetch()"]
        Catalog["axm://tools resource"]
    end

    subgraph "Discovery"
        Discover["discover_tools()"]
        Register["register_tools()"]
        EP["axm.tools entry points"]
    end

    subgraph "Installed Packages"
        Audit["axm-audit (audit)"]
        Init["axm-init (init_check, init_scaffold)"]
        Bib["axm-bib (bib_search, bib_doi, bib_pdf)"]
    end

    Server --> ListTools
    Server --> Verify
    Server --> WebFetch
    Server --> Catalog
    Server --> Discover
    Discover --> EP
    EP --> Audit
    EP --> Init
    EP --> Bib
    Register --> Server
```

## Transport Modes

### stdio (legacy)

The MCP client forks a new `axm-mcp` process per conversation. Each process has its own memory and state.

```mermaid
graph LR
    C1[Conversation 1] -->|fork| P1[axm-mcp process]
    C2[Conversation 2] -->|fork| P2[axm-mcp process]
    C3[Conversation 3] -->|fork| P3[axm-mcp process]
    P1 --> T[axm.tools entry points]
    P2 --> T
    P3 --> T
```

### Streamable HTTP (recommended)

A single persistent server on port 9427 handles all conversations. AST cache, protocol sessions, and keyed locks are shared.

```mermaid
graph LR
    C1[Conversation 1] -->|HTTP| S[axm-mcp server :9427]
    C2[Conversation 2] -->|HTTP| S
    C3[Conversation 3] -->|HTTP| S
    S --> T[axm.tools entry points]
    S --> Cache[AST cache]
    S --> Sessions[Protocol sessions]
```

### Request flow (HTTP)

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant Server as axm-mcp server
    participant FastMCP as FastMCP
    participant Tool as AXM Tool

    Client->>Server: POST /mcp (tool call)
    Server->>FastMCP: Route to registered tool
    FastMCP->>Tool: execute(**kwargs)
    Tool-->>FastMCP: ToolResult
    FastMCP-->>Server: MCP response
    Server-->>Client: JSON response

    Note over Client,Server: GET /health → {"status": "ok", "tools_count": N}
```

## Modules

| Module | Key Symbols | Purpose |
|---|---|---|
| `mcp_app.py` | `mcp`, `_verify_tool()`, `_web_fetch_tool()`, `_tool_catalog()`, `main()` | FastMCP server instance + built-in tools + tool catalog resource |
| `server.py` | `serve()`, `health_check()`, `DEFAULT_PORT` | Streamable HTTP transport — runs the FastMCP instance over HTTP on port 9427 (or `AXM_MCP_PORT`) |
| `concurrency.py` | `KeyedLock` | Per-key asyncio lock manager — prevents concurrent execution of the same session or git operation |
| `discovery.py` | `discover_tools()`, `register_tools()`, `ToolLike`, `_session_lock`, `_git_lock` | Entry point scanning + MCP registration; `protocol_*` and `git_*` tools wrapped with async keyed locks |
| `verify.py` | `verify_project()`, `_enrich_failure()`, `_extract_symbols()` | Orchestrate audit + init check + AST enrichment (impact scores: LOW/MEDIUM/HIGH) |
| `web_fetch.py` | `fetch_page()` | Anti-bot web page fetching via Scrapling (basic / dynamic / stealth) |
| `lifecycle.py` | `find_binary()`, `generate_plist()`, `install()`, `uninstall()` | launchd service management — install/uninstall axm-mcp as a macOS background service |
| `plist_template.py` | `PLIST_TEMPLATE` | launchd plist XML template used by `lifecycle.generate_plist()` |

## Design Decisions

| Decision | Rationale |
|---|---|
| Zero imports from `axm` core | Fully decoupled — `axm-mcp` works with any combination of installed packages |
| `ToolLike` Protocol | Duck typing via `Protocol` — no class inheritance needed |
| Entry points for discovery | Standard Python mechanism, no config files needed |
| `verify` as meta-tool | Single call replaces 3 separate tool invocations |
| AST enrichment of failures | Adds blast-radius context to help agents prioritize fixes |

## Tool Lifecycle

1. **Startup**: `discover_tools()` scans `axm.tools` entry points
2. **Registration**: `register_tools()` wraps each tool as an MCP callable
3. **Resource**: `_tool_catalog()` exposes the tool catalog via `axm://tools` MCP resource
4. **Execution**: MCP client calls tool → wrapper delegates to `tool.execute(**kwargs)` → if `ToolResult.text` is set, returns raw string (rendered as `TextContent`); otherwise returns flattened dict
5. **Verify**: `verify_project()` chains audit → init_check → AST enrichment

## Concurrency Model (HTTP mode)

Multiple conversations run concurrently on the same server. To prevent conflicts:

- **Protocol sessions** are serialized per `session_id` via `KeyedLock`
- **Git operations** are serialized per `repo_path` via `KeyedLock`
- **Graceful shutdown** drains in-flight requests (5s timeout) before exit

## Service Lifecycle (macOS)

```mermaid
graph TD
    Install["axm-mcp install"] --> Plist["Generate plist"]
    Plist --> Load["launchctl bootstrap"]
    Load --> Running["Server running on :9427"]
    Running -->|crash| Restart["Auto-restart (KeepAlive)"]
    Restart --> Running
    Running --> Stop["axm-mcp uninstall"]
    Stop --> Bootout["launchctl bootout"]
    Bootout --> Removed["Plist removed"]
```

| Item | Path |
|---|---|
| Plist | `~/Library/LaunchAgents/io.axm.mcp-server.plist` |
| PID file | `~/.axm/mcp-server.pid` |
| stdout log | `~/Library/Logs/axm-mcp/stdout.log` |
| stderr log | `~/Library/Logs/axm-mcp/stderr.log` |
