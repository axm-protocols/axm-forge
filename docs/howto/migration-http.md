# Migrating from stdio to Streamable HTTP

This guide walks through migrating your axm-mcp setup from the default stdio transport to the persistent Streamable HTTP server.

## Why migrate?

| | stdio | HTTP |
|---|---|---|
| Processes | One per conversation | Single shared server |
| Startup time | Cold `uv sync` each time | Instant (already running) |
| AST cache | Lost between conversations | Shared across all calls |
| Protocol sessions | Per-conversation only | Persistent |
| CPU usage | Risk of zombie processes | Single managed process |

## Prerequisites

- axm-mcp >= 0.11.0
- macOS (launchd integration) or any OS (manual `serve`)

## Step 1 — Start the server

### Option A: launchd service (recommended on macOS)

```bash
axm-mcp install
```

This generates a launchd plist at `~/Library/LaunchAgents/io.axm.mcp-server.plist`, loads it via `launchctl`, and starts the server automatically. The service restarts on crash and starts on login.

### Option B: manual

```bash
axm-mcp serve
```

Starts the server in the foreground on `127.0.0.1:9427`.

To use a different port:

```bash
axm-mcp serve --port 8080
# or
AXM_MCP_PORT=8080 axm-mcp serve
```

## Step 2 — Verify the server is running

```bash
axm-mcp status
```

Expected output:

```
Server running on 127.0.0.1:9427 (42 tools)
```

You can also hit the health endpoint directly:

```bash
curl http://localhost:9427/health
# {"status": "ok", "tools_count": 42}
```

## Step 3 — Update `.mcp.json`

Replace the stdio config with the HTTP config.

**Before** (stdio):

```json
{
  "mcpServers": {
    "axm-mcp": {
      "command": "uv",
      "args": ["run", "axm-mcp"]
    }
  }
}
```

**After** (HTTP):

```json
{
  "mcpServers": {
    "axm-mcp": {
      "type": "url",
      "url": "http://localhost:9427/mcp"
    }
  }
}
```

This file lives at `~/.claude/.mcp.json` (global) or `.mcp.json` at the project root.

## Step 4 — Restart Claude Code

Restart your Claude Code session so it picks up the new `.mcp.json` config. The MCP client will now connect to the HTTP server instead of forking a stdio process.

## Rolling back to stdio

If you need to revert:

1. Restore the stdio `.mcp.json` config (the "Before" block above)
2. Stop the HTTP server:

```bash
axm-mcp stop
```

3. If you installed the launchd service:

```bash
axm-mcp uninstall
```

4. Restart Claude Code

## Troubleshooting

### Server not running

```
$ axm-mcp status
Server not running
```

**Fix**: Start the server with `axm-mcp serve` or reinstall the service with `axm-mcp install`.

If using launchd, check the logs:

```bash
cat ~/Library/Logs/axm-mcp/stderr.log
```

### Port conflict

```
Error: [Errno 48] Address already in use
```

**Fix**: Another process is using port 9427. Either stop that process or use a different port:

```bash
axm-mcp serve --port 9428
```

Update your `.mcp.json` URL to match the new port.

You can also set the port via environment variable:

```bash
export AXM_MCP_PORT=9428
```

### Zombie processes (100% CPU)

This typically happens with leftover stdio processes from before the migration.

**Fix**: Stop the HTTP server and restart it cleanly:

```bash
axm-mcp stop
axm-mcp serve
```

If using launchd:

```bash
axm-mcp uninstall
axm-mcp install
```

### Tools not responding after migration

All path-dependent tools require explicit `path` arguments in HTTP mode (the server has no per-conversation working directory). If a tool returns an error about missing paths, ensure you are passing absolute paths.

### PermissionError — Full Disk Access (macOS)

```
PermissionError: [Errno 1] Operation not permitted
```

Found in `~/Library/Logs/axm-mcp/stderr.log`.

**Cause**: macOS blocks launchd background services from accessing `~/Documents`, `~/Desktop`, and `~/Downloads` without Full Disk Access granted to the binary. Because the launchd plist points to a binary inside a `uv` cache or project virtualenv, the OS sandbox denies access to protected directories.

**Fix options** (in order of preference):

1. **Install the binary in `~/.local/bin/`** (recommended) — this path is outside the protected locations and is not subject to the same FDA restrictions:

   ```bash
   uv tool install axm-mcp
   axm-mcp install
   ```

   `uv tool install` places the binary at `~/.local/bin/axm-mcp`, which `axm-mcp install` will detect and use automatically.

2. **Specify the binary path explicitly** — if the binary already lives at an FDA-exempt path, pass it directly:

   ```bash
   axm-mcp install --binary ~/.local/bin/axm-mcp
   ```

3. **Grant Full Disk Access** — if you need to keep the current binary location, grant Full Disk Access to your terminal application or directly to the `axm-mcp` binary in **System Settings > Privacy & Security > Full Disk Access**.
