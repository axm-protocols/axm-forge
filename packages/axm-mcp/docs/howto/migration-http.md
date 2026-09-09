# Migrate to HTTP Transport

Use Streamable HTTP when several clients need a persistent server process.
The default bind address is loopback. The package does not configure
authentication or TLS; choose a trusted deployment boundary before changing
the host.

## 1. Install the server environment

Install the tool set into an environment whose lifetime outlasts the client:

```bash
uv tool install "axm-mcp[forge]"
```

For a project venv, use its exact `axm-mcp` binary instead. Packages installed
in other environments are not discovered.

## 2. Start in the foreground

```bash
axm-mcp serve --host 127.0.0.1 --port 9427 --no-shared
```

This selects the dedicated policy explicitly. **Use `--port`**, including
when your shell has `AXM_MCP_PORT`: the CLI's default is fixed at 9427.
For multiple profiles/processes, choose distinct ports and PID profiles;
see [configuration](../reference/configuration.md).

Dedicated HTTP can serve multiple clients, but it does not require a separate
write contract from each. For cooperative per-session scopes, use the
[shared-policy setup](../reference/shared-contracts.md), including its
current limitations.

## 3. Check the endpoint

From a second terminal:

```bash
axm-mcp status --host 127.0.0.1 --port 9427
curl --fail http://127.0.0.1:9427/health
```

A real server returns a JSON object with `status: "ok"` and
`tools_count`. That number measures direct registration, not the full
catalog. `status` alone only tests reachability; it can accept a 200
non-JSON page.

## 4. Connect your client

Configure your MCP client's **Streamable HTTP** transport with the URL
`http://127.0.0.1:9427/mcp`. Client-specific configuration schemas differ;
a stdio command definition cannot simply be reused as an HTTP definition.

Reconnect and call `list_tools`, then make the read-only call from the
[Quick Start](../tutorials/quickstart.md#step-3-make-a-read-only-call).
Always pass explicit absolute paths. The server does not adopt a different
working directory for each conversation; implicit paths may only produce a
warning, rather than being rejected.

## Optional: launchd on macOS

After the foreground setup works:

```bash
axm-mcp install --port 9427 --binary /absolute/path/to/axm-mcp
```

This replaces/loads a persistent user service with KeepAlive. Review
[its fixed paths and environment behavior](../reference/configuration.md#macos-launchd-installation)
before using it: shell environment variables are not copied into the plist.

## Roll back to stdio

Restore the client's stdio definition from the Quick Start and reconnect.
Stop the foreground server with Ctrl-C or use `axm-mcp stop` for the
matching profile. If you installed launchd, use `axm-mcp uninstall`;
`stop` alone can trigger its automatic restart.

## Troubleshooting

| Symptom | Check |
|---|---|
| Connection refused | Foreground server logs, bind host, explicit port and the client's URL |
| Address already in use | Select another port and use it consistently in serve/status/client configuration |
| Missing tools | Installed environment, disabled patterns and entry-point loading logs |
| Unbound session in shared mode | MCP session ID and valid contract header; discovery alone does not bind a contract |
| PermissionError on macOS | Filesystem permissions and system privacy settings for the actual service process |
| High CPU or stalled tool | Identify the responsible process/call first; stopping HTTP does not stop unrelated stdio children |

launchd stderr is written to `~/Library/Logs/axm-mcp/stderr.log`.
A different binary location may make environment management easier but does
not itself grant access to protected directories.
