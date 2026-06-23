# CLI Reference

## `axm-config` command

The `axm-config` console script (registered under `[project.scripts]`) is the
shell front end to the resolution layer. It owns the process lifecycle only —
every command body delegates to the same central function used programmatically
and over MCP, so the behavior is identical across surfaces.

| Command | Delegates to | Effect |
| -- | -- | -- |
| `axm-config get <ns> <key>` | `get` | Prints the resolved value (`env > file > default`). |
| `axm-config set <ns> <key> <value>` | `set_` | Persists `key = value` in `~/.axm/<ns>.toml` (atomic, `0600`). |
| `axm-config delete <ns> <key>` | `delete` | Removes `key` from `~/.axm/<ns>.toml` (silent no-op if absent). |
| `axm-config path` | `axm_home` | Prints the resolved `~/.axm` home (created `0700` if absent). |
| `axm-config doctor [<ns>]` | `config_doctor_data` | Prints per-key provenance (`<ns>.<key>: <layer>`); all known namespaces if `<ns>` is omitted. |

```bash
axm-config set research.fred api_key abc123
axm-config get research.fred api_key   # -> abc123
axm-config delete research.fred api_key  # remove the key (no-op if absent)
axm-config path                        # -> /Users/you/.axm
axm-config doctor research.fred        # -> research.fred.api_key: file
```

## Tools

### `config_doctor`

Report config-key provenance for a namespace, read-only. For every visible
key (the union of the namespace's `~/.axm/<ns>.toml` file keys and any
`AXM_<NS>_*` environment variables) it reports which layer would win under
the `env > file > default` precedence — it never reads a value into a
consumer and never mutates any layer.

```bash
axm config_doctor --namespace research.fred
```

The result is a mapping `{"<ns>.<key>": {"layer": env|file|default, "present": bool}}`.
Omit `--namespace` to report every namespace with a `~/.axm/<ns>.toml` file.

Programmatic access shares the exact same central function:

```python
from axm_config.doctor import config_doctor_data

report = config_doctor_data("research.fred")
# {"research.fred.api_key": {"layer": "env", "present": True}, ...}
```

## Validation

Every public surface (`get` / `set_` / `delete` / `load`, and their CLI
counterparts) validates the `namespace` and `key` against safe-segment
patterns before touching disk. Both are **lowercase-only**: a **namespace**
is lowercase-alphanumeric segments joined by dots
(`^[a-z0-9]+(\.[a-z0-9]+)*$`) — uppercase, `_`, and `-` in a namespace are
rejected; a **key** is lowercase-alphanumeric segments joined by *single* `_`
(`^[a-z0-9]+(_[a-z0-9]+)*$`) — uppercase, dots/dashes, and leading/trailing
or doubled `_` in a key are rejected. A path separator, `..` traversal, the
empty string, or a NUL byte raises `ConfigError` — so a config file can never
escape the resolved `~/.axm` home. A `HOME` that itself resolves inside a git
checkout is refused as well.

The per-key env name is derived as `AXM_<NS>_<KEY>` upper-cased, with each
namespace dot folded to a *double* underscore (`a.b` → `AXM_A__B_*`). The
mapping is **provably injective** and always POSIX-valid: lowercase-only
segments make the upper-casing a bijection (so `Demo` cannot collide with
`demo`), a namespace carries no `_` of its own and no `-`, and a key can
never forge a `__` (single-`_`-joined, no edge/doubled `_`) — so a `__` only
ever comes from a namespace dot and the lone single `_` marks the
namespace/key boundary. So `doctor`'s reverse enumeration round-trips it
exactly.

## Python API

Auto-generated API reference is available under [Python API](api/).
