# Runtime settings

Each wrapper reads the listed namespace/key, using its environment equivalent
first. Typed accessors then try the compatibility `AXM_HOME/config.toml`
fallback only if ordinary resolution was missing; see [profiles](../howto/profiles.md).

Except for the three inference helpers, wrappers accept a keyword-only
`default=None`. A non-None caller default replaces the built-in fallback,
subject to the profile relocation rules below. Fallback values are generally
not validated like configured values.

## Paths

| Helper | Namespace/key | Production built-in default | Named-profile unconfigured default |
|---|---|---|---|
| `sessions_root()` | `paths.sessions_root` | `~/axm/sessions` | `<root>/sessions` |
| `quality_dir()` | `paths.quality_dir` | `~/axm/quality` | `<root>/quality` |
| `protocols_dir()` | `paths.protocols_dir` | `~/axm/protocols` | `<root>/protocols` |
| `warden_socket()` | `paths.warden_socket` | `~/.axm/warden.sock` | `<root>/warden.sock` |
| `warden_log_path()` | `warden.log_path` | `~/.axm/warden.log` | `<root>/warden.log` |
| `tickets_db()` | `tickets.db_path` | `~/axm/tickets/tickets.db` | `<root>/tickets/tickets.db` |
| `warden_binary_path()` | `warden.binary_path` | Beside `sys.executable`: `axm-warden` | Same interpreter-relative path |

`<root>` is `~/.axm/profiles/<name>`. The first five rows relocate even a
caller-supplied fallback. For `tickets_db`, an explicit `default` is retained,
including outside the profile. Arbitrary `get_path` keys also retain their
fallback. Configured values, including a configured executable, must resolve
inside the active profile root and outside git repositories.

The `protocols_dir` accessor remains a compatibility path setting. Its presence
does not restore the decommissioned YAML engine or removed hooks.

These functions return paths; they do not create sessions, databases, sockets or
start the warden. Calls may create/tighten the base AXM home while resolving.
An explicit consumer command argument should remain above configuration
resolution rather than being passed as a lower-priority default.

## Warden values

| Helper | Namespace/key | Default | Configured-value validation |
|---|---|---|---|
| `warden_mode()` | `warden.mode` | `"embedded"` | `embedded` or `pull` |
| `warden_max_concurrent()` | `warden.max_concurrent` | `4` | Integer > 0 |
| `warden_park_threshold()` | `warden.park_threshold` | `3` | Integer >= 1 |
| `warden_autostart()` | `warden.autostart` | `True` | Generic boolean conversion |

For example, `AXM_WARDEN_MAX_CONCURRENT` overrides `[warden] max_concurrent`.
These values configure consumers; reading them does not launch a process.

## Inference

| Helper | Namespace/key | Default |
|---|---|---|
| `inference_base_url()` | `inference.base_url` | `http://127.0.0.1:8000/v1` |
| `inference_model()` | `inference.model` | `ornith-ai/Ornith-1.5-9B-MLX-4bit` |
| `inference_origin()` | `inference.origin` | `local` |

The URL and model pass through `get_str`; no URL validation, connectivity check,
model discovery or endpoint normalization is performed. Origin must be exactly
`anthropic`, `google`, `local` or `openai`, otherwise `ConfigError`.
