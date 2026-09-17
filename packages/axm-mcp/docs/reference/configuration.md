# Configuration and service paths

## Select the policy

```toml
[mcp]
serve_mode = "dedicated"
```

The AXM configuration store resolves environment > file > default. For this
setting the environment name is `AXM_MCP_SERVE_MODE`, and the file is
`~/.axm/config.toml`. `AXM_HOME` does not redirect that generic store.
A configuration change takes effect on the next server start, not as a
live reload. For a shared policy, read [the contract and its limits](shared-contracts.md).

## Profiles and ports

| Resource | Production | Other AXM_PROFILE |
|---|---|---|
| CLI PID file | `~/.axm/mcp-server.pid` | Under the axm-config profile root, named `mcp-server.pid` |
| CLI port | `9427`, or `--port` | Also `9427`, or `--port` |
| Daemon descriptor port | `AXM_MCP_PORT`, otherwise `9427` | `AXM_MCP_PORT`, otherwise a port derived from the profile name in the 20000-49151 band |
| Supervisor service ID | `io.axm.mcp` | Deterministic profile-derived suffix |

`resolve_http_port()` is the single seam, and it decides nothing itself: it
delegates to `axm_config.service_port("mcp")`, which keeps `9427` under
production and derives a distinct, restart-stable port per profile elsewhere.
Two profiles therefore no longer land on the same descriptor port. The CLI
still defaults to `9427` whatever the profile, so choose explicit, distinct
`--port` values when starting more than one instance that way, and pass the
same port to `status`.

The `axm.daemons` entry point calls `daemon_descriptor()`. It returns a
launch plan whose argv includes `serve --port N`, whose environment
preserves `AXM_PROFILE` and an explicit `AXM_MCP_PORT`, and whose PID/log
paths follow the profile. Its probe description contains the HTTP base URL;
the server's health endpoint itself is `/health`.

## macOS launchd installation

```bash
axm-mcp install --port 9427 --binary /absolute/path/to/axm-mcp
```

This writes a plist, attempts a best-effort bootout of an existing instance,
then bootstraps the service. It can replace and restart an existing install.
A bootstrap failure exits 1 but leaves the written plist and log directories.

| Artifact | Path |
|---|---|
| Label | `io.axm.mcp-server` |
| Plist | `~/Library/LaunchAgents/io.axm.mcp-server.plist` |
| stdout | `~/Library/Logs/axm-mcp/stdout.log` |
| stderr | `~/Library/Logs/axm-mcp/stderr.log` |

The generated plist enables RunAtLoad and KeepAlive. It passes `serve --port`
but contains **no EnvironmentVariables block**. It does not propagate the
invoking shell's AXM profile, facade, port or policy environment automatically.
The launchd installer has one fixed label and plist path; it is not the
profile-aware AXM supervisor descriptor. Do not use repeated `install` calls
as a way to create one launchd service per profile.

Without `--binary`, discovery prefers an existing
`~/.local/bin/axm-mcp`, then PATH. It checks that preferred file exists,
not that it is the environment you intended or has your optional tools.
Use the exact binary from the environment where those packages are installed.

`uninstall` attempts bootout and removes the plist even if launchctl reports
the service was already stopped. It does not remove the package, logs or
configuration. The installed binary's filesystem permissions still apply;
moving a binary to `~/.local/bin` is not a guarantee of macOS Full Disk Access.

## Startup consistency

Start a fresh process after changing the policy. Discovered tools, catalog
wrappers and the internal shared registration flag are created during import.
Reusing an imported application while changing environment variables can
produce different registration and middleware policies; the CLI's normal
one-process-per-start path avoids that reuse.
