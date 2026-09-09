# CLI reference

The installed binary is `axm-mcp`. It manages the server process; MCP tools
are called by an MCP client. The package declares no `axm.tools` entry points:
its built-ins are registered inside the server, so installing it alone does
not add `axm verify` or `axm web_fetch` to the generic AXM CLI.

## Commands

| Command | Parameters | Behavior |
|---|---|---|
| `axm-mcp` | none | Run MCP over stdio until the client closes the connection |
| `axm-mcp serve` | `--host` (`127.0.0.1`), `--port` (`9427`), `--shared / --no-shared` | Run Streamable HTTP at `/mcp`, with `/health` |
| `axm-mcp status` | `--host` (`127.0.0.1`), `--port` (`9427`) | HTTP GET to `/health`, timeout 3 seconds |
| `axm-mcp stop` | none | Send SIGTERM to the active profile's recorded process |
| `axm-mcp install` | `--port` (`9427`), `--binary PATH` | Write and load the macOS launchd service |
| `axm-mcp uninstall` | none | Unload the launchd service and remove its plist |

Every subcommand accepts `--help`. There is no `--version` flag.

### serve

`--port` must be between 1 and 65535. **Pass the port explicitly**:
the CLI passes its default `9427` to the server even when `AXM_MCP_PORT`
is set. `status` and `install` also default to `9427`. The environment
variable is used by the lower-level server API when no port is provided and
by the AXM daemon descriptor; these are different entry points.

The serving policy resolves explicit `--no-shared` → `AXM_MCP_SERVE_MODE`
→ `[mcp] serve_mode` in AXM configuration → `dedicated`.
Only `shared` and `dedicated` are valid. **The explicit `--shared` flag
currently exits 1**, even on `serve`, with a message referring to stdio.
Use `AXM_MCP_SERVE_MODE=shared axm-mcp serve --port 9427` to start the
shared policy. Keep the facade enabled; see [shared contracts](shared-contracts.md).

Before starting, the command checks the profile's PID file and refuses if it
identifies a live axm-mcp process. It writes its own PID, and on exit removes
the file only if it still contains that PID. This protects an established
server against an ordinary second start; the check/write sequence has no
interprocess lock and does **not** guarantee exclusion for simultaneous starts.
Cleanup requires normal stack unwinding: in the tested MCP 1.30/Uvicorn 0.52
combination, SIGTERM shutdown can leave a stale PID file.

### status

HTTP errors and non-200 replies exit 1. A 200 JSON object prints
`Server running on HOST:PORT (N tools)`, where `N` comes from
`tools_count` or is `?` when absent. A 200 non-JSON body also prints a
running server with `?` and exits 0. A JSON array or scalar can raise an
uncaught attribute error. This is a reachability probe, not a verified
identity, authorization or tool-execution check.

The real server's health object is:

```json
{"status": "ok", "tools_count": 7}
```

The count is illustrative: it counts **directly registered MCP tools**,
including meta-tools, rather than all facade-dispatchable entries.

### stop

The command reads the active profile's PID file, checks process existence
and looks for the `axm-mcp` substring in its command line (`/proc` when
available, otherwise `ps`). Missing, stale or unrecognized PIDs exit 1;
stale/unrecognized PID files are removed without signalling the process.
This is a command-line marker check, not cryptographic process identity.

On success it sends SIGTERM and removes the PID file immediately; it does
not wait for process exit. A launchd service with KeepAlive may restart:
use `uninstall` to remove that service.

### Exit codes

`0` means the command completed its own action, not that all tools are
healthy. Explicit lifecycle errors generally exit `1`; CLI parsing errors
and uncaught exceptions can have other diagnostics. Tool failures are carried
by MCP results and are not a server CLI exit code.

## Environment variables

| Variable | Consumer / effect |
|---|---|
| `AXM_MCP_FACADE` | Default enabled. Trimmed, case-insensitive `0`, `false`, `no` disable the facade; other values enable it |
| `AXM_DISABLE_TOOLS` | Comma-separated, whitespace-trimmed names/globs excluded **before loading** installed `axm.tools` entry points |
| `AXM_MCP_SERVE_MODE` | `shared` or `dedicated`; outranks the configuration file |
| `AXM_PROFILE` | Selects the profile-scoped PID path; unset means `production` |
| `AXM_MCP_PORT` | Used by the daemon descriptor and lower-level port resolution; does not override the CLI's `--port` default |
| `AXM_MCP_SHARED` | Internal registration switch set by `serve`; do not set it independently of the serving policy |

Disabling discovered entries does not disable the server's built-in
`verify`, `web_fetch` or `list_tools`. Discovery and facade registration
happen at import/startup; restart after changing installed packages or these
switches. [Configuration and service paths](configuration.md) details the
separate CLI, supervisor and launchd behavior.
