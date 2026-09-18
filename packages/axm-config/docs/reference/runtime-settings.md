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

Every state helper above except `warden_binary_path` also accepts a keyword-only
`profile=`. `sessions_root(profile="scratch")` answers for that profile without
exporting `AXM_PROFILE`; `profile="production"` returns the caller default
unprefixed, since the default profile owns no root; `profile=None` (the default)
keeps the active-profile behaviour unchanged. The containment guard then applies
to the *requested* profile's root, and the `ConfigError` names that profile.
`get_path(key, default, *, profile=...)` takes the same keyword.

The `protocols_dir` accessor remains a compatibility path setting. Its presence
does not restore the decommissioned YAML engine or removed hooks.

These functions return paths; they do not create sessions, databases, sockets or
start the warden, and resolving one creates nothing at all: the locations are
computed through the non-creating `axm_home_path()`, so reading configuration
never materialises `~/.axm`.
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

## Network listening points

| Helper | Namespace/key | Historical variable | Production built-in default | Named-profile unconfigured default |
|---|---|---|---|---|
| `service_port("mcp")` | `network.mcp_port` | `AXM_MCP_PORT` | `9427` | Derived from the profile name |
| `service_port("orison_web")` | `network.orison_web_port` | none | `8840` | Derived from the profile name |

`service_port(service)` takes one positional service id and accepts no
`default=` keyword: the registry above *is* the default. In production, with
nothing configured, the adopted number is returned unchanged.

Under a named profile the unconfigured fallback is derived rather than refused.
The profile name selects a block of `[20000, 49151]` (registered, non-privileged
and clear of the ephemeral range) through a `hashlib.blake2b` digest, and the
service's rank in the registry is the offset inside that block. The digest is
stable across processes and machines, so a restart resolves the same number;
two services of one profile are distinct by construction; two profile names
differ unless their digests collide, which is not prevented.

The derived number is supplied only as the `default` argument of `get_int`, so
precedence is the usual one: `AXM_NETWORK_MCP_PORT=5555` outranks both the
adopted `9427` and any derived value, and `[network] mcp_port` in the selected
profile file sits between the two.

A service whose registry row names a historical variable inserts exactly one
extra layer. `AXM_MCP_PORT` is read after the derived `AXM_NETWORK_MCP_PORT`
and before any configured value, under every profile, so the full order for
`mcp` is `AXM_NETWORK_MCP_PORT` > `AXM_MCP_PORT` > `[network] mcp_port` >
adopted or derived number. A service with no historical variable, such as
`orison_web`, resolves exactly as before. An unregistered service id raises
`ConfigError` naming it, before any resolution is attempted.

These helpers return a number. They bind no socket, reserve nothing and do not
check availability. Only services listening on TCP are registered; the warden
binds a Unix socket and appears under [Paths](#paths) instead.

## Inference

| Helper | Namespace/key | Default |
|---|---|---|
| `inference_base_url()` | `inference.base_url` | `http://127.0.0.1:8000/v1` |
| `inference_model()` | `inference.model` | `ornith-ai/Ornith-1.5-9B-MLX-4bit` |
| `inference_origin()` | `inference.origin` | `local` |

The URL and model pass through `get_str`; no URL validation, connectivity check,
model discovery or endpoint normalization is performed. Origin must be exactly
`anthropic`, `google`, `local` or `openai`, otherwise `ConfigError`.
