# Migrating from stdio to Streamable HTTP

This guide walks through migrating your axm-mcp setup from the default stdio transport to the persistent Streamable HTTP server.

## Why migrate?

| | stdio | HTTP |
|---|---|---|
| Processes | One per conversation | Single shared server |
| Startup time | One `uvx` resolve per conversation (cached, fast) | Instant (already running) |
| AST cache | Lost between conversations | Shared across all calls |
| Protocol sessions | Per-conversation only | Persistent |
| CPU usage | Risk of zombie processes | Single managed process |

## Concurrency model (what "shared" really means)

The HTTP server serves **many conversations from one process**, so it is
explicitly designed not to let one slow call stall the others:

- **Sync tools run off the event loop.** In HTTP mode every tool's synchronous
  body is offloaded to a worker thread (`asyncio.to_thread`), so a multi-minute
  `verify` cannot freeze `/health`, keep-alives, or other conversations.
- **Per-key serialization.** Calls that mutate the same resource *are*
  serialized on purpose: `git_*` tools by (normalized) repo path, `protocol_*`
  tools by `session_id`. Two conversations committing to the same repo take
  turns; unrelated repos run in parallel.
- **Lock timeout is graceful.** If a lock cannot be acquired within its timeout
  (30 s), the call returns a structured `{success: false, error: "… busy, retry"}`
  rather than a raw protocol error.

This holds whether a tool is called directly or through `axm_call` — both go
through the same execution path.

Here, “shared” describes one HTTP process serving several clients. It is not the
`serve --shared` authorization policy: that policy requires a per-session identity
and write-contract binding, so the current CLI refuses it instead of granting an
undeclared default perimeter. The policy can also come from AXM configuration;
configuring `shared` has the same safety guard as passing `--shared`.

## Prerequisites

- A recent `axm-mcp` with the `serve`/`status`/`stop` subcommands (run
  `axm-mcp --help` to confirm they are present)
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

### Select the serving policy without changing the service command

The default policy is `dedicated`. To configure it persistently, edit
`~/.axm/config.toml`:

```toml
[mcp]
serve_mode = "dedicated"
```

Resolution order is an explicit CLI value, `AXM_MCP_SERVE_MODE`, the
`[mcp] serve_mode` value, then the `dedicated` default. Only `shared` and
`dedicated` are accepted. The file is read for every `serve` invocation, so an
installed launchd service can return to `dedicated` on its next start after a
configuration edit; its command line and plist do not need to be regenerated.
The current CLI still refuses `shared` when no per-session identity is available.

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

**Before** (stdio — the default setup from the [Quick Start](../tutorials/quickstart.md)):

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

This file lives at `~/.claude.json` (global, applies to all projects) or
`.mcp.json` at a project root (project-scoped — takes precedence over the global
file when present).

## Step 4 — Restart Claude Code

Restart your Claude Code session so it picks up the new `.mcp.json` config. The MCP client will now connect to the HTTP server instead of forking a stdio process.

## Reverting the serving policy

If a configured `shared` policy prevents startup, restore the safe policy by
editing only `~/.axm/config.toml`:

```toml
[mcp]
serve_mode = "dedicated"
```

The next launchd restart or manual `axm-mcp serve` call reads the new value with
the same command line. An `AXM_MCP_SERVE_MODE` environment value still outranks
the file and must be removed or changed if one is set.

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
