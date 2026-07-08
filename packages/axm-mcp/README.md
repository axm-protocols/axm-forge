<p align="center">
  <img src="https://raw.githubusercontent.com/axm-protocols/axm-forge/main/assets/logo.png" alt="AXM Logo" width="180" />
</p>

<p align="center">
  <strong>axm-mcp — MCP server for the axm-protocols ecosystem</strong>
</p>

<p align="center">
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml"><img src="https://github.com/axm-protocols/axm-forge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://forge.axm-protocols.io/audit/"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/axm-audit.json" alt="axm-audit"></a>
  <a href="https://github.com/axm-protocols/axm-forge/actions/workflows/axm-quality.yml"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/axm-protocols/axm-forge/gh-pages/badges/axm-mcp/coverage.json" alt="Coverage"></a>
  <a href="https://pypi.org/project/axm-mcp/"><img src="https://img.shields.io/pypi/v/axm-mcp" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <a href="https://forge.axm-protocols.io/"><img src="https://img.shields.io/badge/docs-live-brightgreen" alt="Docs"></a>
</p>

---

## Features

- 🔌 **Auto-discovery** — Finds all `axm.tools` entry points from installed packages
- 🛠️ **MCP bridge** — Exposes discovered tools as Model Context Protocol callables
- 🔎 **Compact facade** — Four meta-tools (`axm_search` / `axm_describe` / `axm_call` / `axm_capabilities`) index the full catalog and keep the `tools/list` payload small (toggle via `AXM_MCP_FACADE`)
- ✅ **Verify** — One-shot project quality check: audit + init check + AST enrichment
- 🌐 **Web fetch** — Anti-bot web page fetching via Scrapling (basic / dynamic / stealth)
- 📋 **List tools** — Built-in `list_tools` meta-tool to enumerate all available tools and their descriptions

## Installation

Connect the server to your MCP client (Claude Code, IDE…) in one command — no
manual install, `uvx` fetches the latest version on demand:

```bash
claude mcp add --scope user axm-mcp -- uvx --python 3.12 --from "axm-mcp[all]@latest" axm-mcp
```

`--scope user` installs it globally (available in every session). Drop it to enable AXM per-project instead — the server then loads only in the directory where you run the command.

Prefer editing `.mcp.json` by hand? Add:

```json
{
  "mcpServers": {
    "axm-mcp": {
      "command": "uvx",
      "args": ["--python", "3.12", "--from", "axm-mcp[all]@latest", "axm-mcp"]
    }
  }
}
```

The `[all]` extra is what pulls in the actual tools (`audit`, `ast_*`,
`git_commit`, …); the bare `axm-mcp` package is only the server shell. See the
**[Quick Start](https://forge.axm-protocols.io/mcp/tutorials/quickstart/)** for
the full walkthrough and why each flag matters.

## Server Modes

axm-mcp supports two transport modes. **stdio** (above) is the simple default —
one server process per conversation, works everywhere. **HTTP** is an advanced
option for running a single shared persistent server.

| Mode | Command | Client config | Use case |
|---|---|---|---|
| **stdio** (default) | `axm-mcp` | `uvx --from "axm-mcp[all]@latest" axm-mcp` | Simple, one process per conversation |
| **HTTP** (advanced) | `axm-mcp serve` | `{"type": "url", "url": "http://localhost:9427/mcp"}` | Single shared server, persistent cache |

For the HTTP setup, see [Migrate to HTTP Transport](https://forge.axm-protocols.io/mcp/howto/migration-http/).

## CLI Commands

| Command | Description |
|---|---|
| `axm-mcp` | Start in **stdio** mode (default) |
| `axm-mcp serve [--host HOST] [--port PORT]` | Start Streamable HTTP server (default port `9427`) |
| `axm-mcp status [--host HOST] [--port PORT]` | Check whether the HTTP server is running |
| `axm-mcp stop` | Send SIGTERM to the running HTTP server. Verifies the PID file's process is really `axm-mcp` (via `ps` cmdline) before signalling; if the PID was reused by another process, it refuses to kill it and cleans up the stale PID file |
| `axm-mcp install [--port PORT] [--binary PATH]` | Install axm-mcp as a launchd service (macOS) |
| `axm-mcp uninstall` | Remove the launchd service |

The HTTP transport exposes a `/health` endpoint returning `{"status": "ok", "tools_count": N}`.
Port can also be set via the `AXM_MCP_PORT` environment variable.

## Service Management (macOS)

`axm-mcp` can run as a persistent background service managed by launchd:

```bash
# Install and start the service
axm-mcp install

# Remove the service
axm-mcp uninstall
```

`install` locates the `axm-mcp` binary, generates a launchd plist, and loads it via `launchctl`.
`uninstall` unloads the service and removes the plist file.

## MCP Tools

By default (`AXM_MCP_FACADE=1`) the server keeps the `tools/list` payload small
by exposing a **compact facade** — four meta-tools that index the full catalog —
plus a *hot path* of frequently-used tools that opt in via `expose_directly`, and
the always-on built-ins (`verify`, `web_fetch`, `list_tools`). Every other
discovered tool stays reachable through `axm_call`. Set `AXM_MCP_FACADE=0` to fall
back to the legacy behaviour (register every discovered tool directly).

To trim a shared server's surface, set `AXM_DISABLE_TOOLS` to a comma-separated
list of tool names or glob patterns to exclude at discovery time
(e.g. `AXM_DISABLE_TOOLS=bib_*,ticket_*,ast_dead_code`). See the
[CLI reference](docs/reference/cli.md#environment-variables) for the full
environment-variable table.

| Facade meta-tool | Description |
|---|---|
| `axm_search` | Search the tool catalog by keyword/tag → name + summary + domain + tags |
| `axm_describe` | Full invocation contract (typed params + docstring) for one tool |
| `axm_call` | Execute any tool by name and return its text output |
| `axm_capabilities` | List tools grouped by domain |

| Built-in / discovered tool | Package | Description |
|---|---|---|
| `list_tools` | built-in | List all available tools (always enumerates the full surface) |
| `verify` | built-in | One-shot audit + init check + AST enrichment |
| `web_fetch` | built-in | Fetch web pages with anti-bot bypass (basic / dynamic / stealth) |
| `audit` | `axm-audit` | Code quality audit (lint, types, complexity, security) |
| `init_check` | `axm-init` | 49 governance checks against AXM gold standard |
| `init_scaffold` | `axm-init` | Scaffold a new Python project |
| `bib_search` | `axm-bib` | Search academic papers by title |
| `bib_resolve` | `axm-bib` | Resolve a DOI/arXiv ref → BibTeX |
| `bib_pdf` | `axm-bib` | Download paper PDF |
| `bib_extract` | `axm-bib` | Extract text from PDF |

## Development

This package is part of the **axm-forge** workspace.

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run --package axm-mcp --directory packages/axm-mcp pytest -x -q
```

## License

Apache-2.0 — © 2026 Gabriel Jarry
