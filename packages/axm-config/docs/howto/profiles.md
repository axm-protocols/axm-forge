# Use profiles and check isolation

## Select a store

`AXM_PROFILE` is read at call time. Unset or empty means `production`.

| Selection | Store | `profile_root()` |
|---|---|---|
| production | `~/.axm/config.toml` | `None` |
| docs-demo | `~/.axm/profiles/docs-demo/config.toml` | `~/.axm/profiles/docs-demo` |

Names follow `^[a-z][a-z0-9-]{0,31}$`: `ci-2` is valid;
`Dev`, `1dev` and `dev_x` raise `ConfigError`.

```bash
AXM_PROFILE=docs-demo axm-config get research.demo timeout
```

The generic resolver, store, model loading and namespace enumeration use the
selected file and its profile-local legacy files. A missing named-profile file
does not fall back to production. Environment overrides are shared between
profiles unless the launching process scopes them.

`axm_home()` creates/tightens `~/.axm` to mode `0700` on POSIX, and only the
code that persists state calls it: a path helper or a store *read* resolves the
location through `axm_home_path()` and creates nothing. The home is therefore
materialised on first write, and the named profile directory with it, with
normal `mkdir`/umask permissions under that private parent.
`axm-config path` prints the base home, not the selected config file.

## Propagate the selection

`profile_env()` returns only `{"AXM_PROFILE": current_profile()}`.
Merge that overlay into a child process's environment; it is not a complete
environment and does not carry other AXM overrides. Avoid changing process-global
`os.environ` concurrently to switch profiles: the selection is not a per-request
or thread-local context.

## Read the isolation report

```bash
axm profile_isolation --profile scratch
```

The report answers through the resolver instead of recomposing a convention:
its six entries are `tickets_db`, `warden_socket`, `warden_log_path`,
`sessions_root`, `quality_dir` and `protocols_dir` called with the requested
profile, so `env > file > default` and the containment guard apply exactly as
they do at runtime. A configured `[paths] sessions_root` is therefore the value
printed, not a convention-derived sibling. The calculation still creates
nothing: it resolves through the non-creating `axm_home_path()` and never calls
`axm_home()`. `profile_root` names the convention root
`<axm home>/profiles/<name>` for the requested profile, rooted at `~/.axm`:
`AXM_HOME` selects only the compatibility `config.toml` that is read, never
this layout.

`isolated` and `escapes` are derived from those reported paths by
`is_isolated(root, paths)` -- every location not contained by `profile_root` is
named in the sorted `escapes` list. Run the diagnostic without a profile and
the default one reports `isolated: false` with all six locations listed as
escapes: `profile_root_for("production")` is `None`, the resolver places nothing
under `profiles/production`, and the report now says so instead of announcing a
profile tree nobody writes to. Production state is deliberately shared; that
answer is the truth, not a regression.
`is_isolated(root, paths)` is a lexical `Path.is_relative_to` check; it does
not resolve symlinks or `..` segments. Supply normalized paths when using it
directly, and do not treat its result as a filesystem security audit.

## Ask what another profile would use

Reading a location for a profile you are not running under no longer requires
exporting `AXM_PROFILE` in the current process:

```python
from axm_config import profile_root_for, sessions_root, tickets_db

profile_root_for("scratch")        # ~/.axm/profiles/scratch
profile_root_for("production")     # None -- the default profile owns no root
sessions_root(profile="scratch")   # ~/.axm/profiles/scratch/sessions
tickets_db(profile="scratch")      # ~/.axm/profiles/scratch/tickets/tickets.db
```

`tickets_db`, `warden_socket`, `warden_log_path`, `sessions_root`, `quality_dir`
and `protocols_dir` all take that keyword, and so does the generic
`get_path(key, default, *, profile=...)`. Three properties make the answer safe
to print in a read-only report:

- nothing is created, neither `~/.axm` nor the profile directory;
- `AXM_PROFILE` is neither read for the decision nor written, so a concurrent
  resolution in the same process is unaffected;
- configured overrides *are* honoured, and a configured value escaping the
  requested root raises `ConfigError` naming that profile rather than the active
  one. `profile_isolation` reports exactly these values, because it calls these
  same accessors.

`profile="production"` is the deliberate exception: the default profile owns no
root, so the caller default is returned unprefixed, exactly as a production
resolution does. Omit the keyword entirely and resolution is byte-for-byte the
active-profile behaviour described above.

## Run two installations side by side

An application installed under its own profile needs a listening point, not only
state directories. Ask the profile for one instead of demanding it from the
operator:

```python
from axm_config import service_port

port = service_port("mcp")  # 9427 in production, profile-derived otherwise
```

Nothing has to be configured. Under `AXM_PROFILE=alpha` the number is derived
from the profile name, is the same on every restart, and differs from the one
the same service gets under `AXM_PROFILE=beta`. Production is untouched: it
still resolves the adopted default.

Pin a port explicitly when you must; the usual precedence applies.

```bash
AXM_PROFILE=alpha AXM_NETWORK_MCP_PORT=5555 my-service
```

An installation that already exports the historical `AXM_MCP_PORT` keeps working
as is: it is read after `AXM_NETWORK_MCP_PORT` and before any configured
`[network] mcp_port`, under every profile. There is nothing to migrate; prefer
the derived name for new deployments, and set only one of the two, since the
derived name wins when both are present.

`service_port` returns a number; it binds nothing and does not check that the
port is free. Two different profile names are unlikely to collide, but nothing
prevents it, so a deployment that cannot tolerate a clash should still configure
the value. See [runtime settings](../reference/runtime-settings.md) for the
registered services.

## AXM_HOME is not a store override

`axm_home`, `NamespaceStore`, `get`, `set_`, `load` and profile storage
derive their home from `Path.home() / ".axm"` and ignore `AXM_HOME`.

Typed accessors have a different compatibility behavior: after the normal
environment and selected-profile file resolution finds nothing, they try
`AXM_HOME/config.toml` before the caller default. That fallback reads a
top-level namespace table, does not select `profiles/<name>`, and reports
invalid/unreadable TOML as `ConfigError`. It does not bypass the normal store
lookup. Therefore setting `AXM_HOME` alone cannot safely sandbox ordinary
configuration reads or writes.

Configured paths must be outside a git checkout and, with a named profile,
inside its resolved root. Registered state defaults relocate to that root;
arbitrary caller defaults remain unchanged. In particular,
`tickets_db(default=...)` can retain an external fallback, and the default
warden executable remains beside the interpreter. See
[runtime settings](../reference/runtime-settings.md) for the exact mapping.
