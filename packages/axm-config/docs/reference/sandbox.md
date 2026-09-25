# Session sandbox

`axm_config.sandbox` moves the six AXM state paths to a temporary root. It is
the primitive a test session uses so it never writes into the real `~/axm` or
`~/.axm` state.

```python
from pathlib import Path

from axm_config.sandbox import activate_sandbox, deactivate_sandbox

sandbox = activate_sandbox(Path("/tmp/axm-session"))
try:
    ...  # sessions_root(), tickets_db(), ... now resolve under /tmp/axm-session
finally:
    deactivate_sandbox(sandbox)
```

## API

| Symbol | Contract |
|---|---|
| `activate_sandbox(root, environ=None) -> SessionSandbox` | Checks the launch variables, then publishes the sandbox in `environ` (default `os.environ`) and removes `AXM_PROFILE`. It creates no directory: the caller creates and deletes `root`. |
| `deactivate_sandbox(sandbox, environ=None) -> None` | Restores the `AXM_SANDBOX_*` and `AXM_PROFILE` values recorded at activation. Nested sandboxes therefore unwind correctly. |
| `active_sandbox(environ=None) -> SessionSandbox \| None` | Rebuilds the sandbox from the environment. Returns `None` when `AXM_SANDBOX_ROOT` is absent. |
| `SessionSandbox` | Frozen dataclass with fields `root`, `launch_home`, `launch_profile` and `launch_axm_home`. |
| `SandboxEscapeError` | A `ConfigError`, raised at activation and naming the offending variable. |

## Environment keys

The sandbox is stored only in the environment, never in module state. A child
process (a CLI, `python -c`, a warden) therefore rebuilds the same sandbox and
the same launch profile.

| Key | Holds |
|---|---|
| `AXM_SANDBOX_ROOT` | The sandbox root. Its presence is what makes a sandbox active. |
| `AXM_SANDBOX_LAUNCH_HOME` | `HOME` at activation. |
| `AXM_SANDBOX_LAUNCH_PROFILE` | `AXM_PROFILE` at activation (empty when unset). `current_profile()` returns it while `AXM_PROFILE` is absent. |
| `AXM_SANDBOX_LAUNCH_AXM_HOME` | `AXM_HOME` at activation (empty when unset). |

## Sandboxed layout

| Helper | Namespace/key | Path under the root |
|---|---|---|
| `sessions_root()` | `paths.sessions_root` | `sessions` |
| `quality_dir()` | `paths.quality_dir` | `quality` |
| `protocols_dir()` | `paths.protocols_dir` | `protocols` |
| `warden_socket()` | `paths.warden_socket` | `w.sock` (short, to fit the 104-byte `AF_UNIX` limit) |
| `tickets_db()` | `tickets.db_path` | `tickets/tickets.db` |
| `warden_log_path()` | `warden.log_path` | `warden.log` |

## Resolution precedence

While a sandbox is active, these six keys resolve in the following order. The
first rule that applies wins:

1. **`AXM_PROFILE` is set, or `HOME` differs from the launch `HOME`.** All six
   keys fall back to ordinary [runtime-settings](runtime-settings.md)
   resolution. This includes the `config.toml` under that `HOME` and profile
   containment.
2. **The key's own variable is set** (for example `AXM_TICKETS_DB_PATH`). Its
   value is used for that key only, resolved through `resolve_safe`. No profile
   containment applies.
3. **`AXM_HOME` differs from the launch value and its `config.toml` sets the
   key.** That value is used.
4. **Otherwise** the sandbox path from the table above is returned.

For these keys, neither `~/.axm/config.toml` nor the `config.toml` in the
launch `AXM_HOME` is ever read. Because `AXM_PROFILE` is removed at activation,
a test that sets it again is detected, even to the launch value.

## Escape check

`activate_sandbox` resolves each launch variable that is set among the six
(`AXM_PATHS_SESSIONS_ROOT`, `AXM_PATHS_QUALITY_DIR`, `AXM_PATHS_PROTOCOLS_DIR`,
`AXM_PATHS_WARDEN_SOCKET`, `AXM_TICKETS_DB_PATH`, `AXM_WARDEN_LOG_PATH`). If
one resolves to `<HOME>/axm` or `<HOME>/.axm`, or below either, it raises
`SandboxEscapeError`. Symlinks are resolved first, so on macOS `/var` becomes
`/private/var` before the comparison.

Without `AXM_SANDBOX_ROOT`, every resolver behaves exactly as described in
[runtime settings](runtime-settings.md).
