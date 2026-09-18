# Public Python contracts

Import the public surface from `axm_config`. The [API page](api.md) renders
every root export, plus the separately registered diagnostic tool.

## Generic resolution

| Function | Contract |
|---|---|
| `get(namespace, key, *, default=None)` | Environment > selected file > supplied default. Environment values stay strings; file values retain TOML types. |
| `get_file(namespace, key, *, default=None)` | Reads persisted/compatible file data without environment overrides. |
| `set_(namespace, key, value)` | Writes a TOML-compatible value; `None` delegates to deletion. Unsupported TOML values may raise serialization errors. |
| `delete(namespace, key)` | Removes a key; a legacy fold may occur even when the key is absent. |
| `load(namespace, model)` | Resolves each model field name and calls Pydantic validation; unresolved fields are omitted. |
| `validate_segment(value, *, kind="segment")` | Validates a namespace or key; other kinds (including the default) use the namespace grammar. Returns the string or raises `ConfigError`. |

An existing empty environment string still wins. Resolution is not cached.
A malformed/unreadable TOML file generally behaves like an empty store.
See [persistence limits](../explanation/architecture.md) for the consequences
on the next write and the parent-namespace deletion defect.

### Names and environment mapping

- Namespace: `^[a-z0-9]+(\.[a-z0-9]+)*$`.
- Key: `^[a-z0-9]+(_[a-z0-9]+)*$`.
- Variable: `AXM_<UPPER_NAMESPACE_WITH_DOTS_AS_DOUBLE_UNDERSCORES>_<UPPER_KEY>`.

Thus `research.demo` / `base_url` maps to `AXM_RESEARCH__DEMO_BASE_URL`.
Uppercase, dashes and underscores in namespace names are rejected. Keys do not
allow dots, dashes, doubled or edge underscores. These grammars make the mapping
injective; an underscore namespace is not an alias of a dotted namespace.

### Errors

`ConfigError(RuntimeError)` covers invalid names, typed values and model
validation failures. `UnsafeHomeError(ConfigError)` represents a home resolving
inside a git checkout. `resolve_safe(target)` independently returns a resolved
Path or raises `ValueError` for an in-repository target. Filesystem errors can
still propagate, especially on directory creation and writes; not every
exception is normalized by the Python layer.

## Home and profiles

`axm_home()` resolves and creates `~/.axm`, tightening POSIX permissions to
`0700`. It does not itself call `resolve_safe`; the store applies that guard to
its own resolved home. No general `AXM_HOME` override exists.

`axm_home_path()` returns the same resolved `~/.axm` path and creates nothing.
It is the read-only counterpart: path resolution and the store's read path go
through it, while every code path that persists state still calls `axm_home()`.

`current_profile()`, `profile_root()`, `profile_config_path()` and
`profile_env()` select and propagate the active profile.
`profile_root_for(profile)` answers the same question for an arbitrary profile:
`None` for `production`, `axm_home_path() / "profiles" / <profile>` otherwise,
whatever `AXM_PROFILE` holds. It creates nothing, ignores `AXM_HOME` and still
raises `ConfigError` on an invalid name.
`profile_isolation(profile=None)` returns `ProfileIsolation`
(`profile`, `profile_root`, `paths`, `isolated`, `escapes`). Each of the six
`paths` entries is the matching state accessor called with that profile, so the
report and the runtime resolve identically, configured overrides included.
`profile_root` is the convention root `axm_home_path() / "profiles" / <profile>`
and stays a plain `Path` even for `production`, which owns no root and therefore
reports `isolated=False` with its six locations as `escapes`. Nothing is
created. `is_isolated(root, paths)` returns `(bool, sorted_escape_names)` over
those reported paths.
The [profile guide](../howto/profiles.md) shows how to read the report.

## Typed values and runtime helpers

`get_path(key, default, *, namespace=PATHS_NAMESPACE, profile=None)`,
`get_int(key, default, *, namespace=PATHS_NAMESPACE, env_aliases=())`,
`get_bool(key, default, *, namespace=PATHS_NAMESPACE)` and
`get_str(key, default, *, namespace=PATHS_NAMESPACE)` share the additional
`AXM_HOME` fallback. `PATHS_NAMESPACE == "paths"`.

- Integers accept native `int` (not bool) or an integer string.
- Booleans accept native bool or case-insensitive
  `1/true/yes/on/0/false/no/off`; generic `get_bool` does not strip whitespace.
- Strings convert configured values with `str`.
- Configured paths accept str/Path, expand `~`, resolve and enforce the
  repository/profile guards. An unconfigured caller fallback is returned
  unchanged unless it is one of the registered profile-relative defaults.

`get_path` alone accepts `profile`: a keyword-only profile name applying the
profile-relative convention and the containment guard for the *requested*
profile instead of the active one. `None` (the default) means the active
profile, so every existing call site resolves unchanged; `"production"` owns no
root and therefore returns the caller default unprefixed. The six state
accessors and `service_port` forward the same keyword. Nothing is created and
`AXM_PROFILE` is neither read for the decision nor written.

`get_int` alone accepts `env_aliases`: a keyword-only sequence of historical
environment variable names, consulted after the derived
`AXM_<NAMESPACE>_<KEY>` and before any file value, the first one set winning.
It defaults to an empty tuple, so every other accessor and every existing call
site resolves unchanged.

`service_port(service, *, profile=None)` resolves a profile's TCP listening
point for a registered service id (`mcp`, `orison_web`) in the `network`
namespace. It takes one positional argument and no `default=`: the registry
supplies the production number, a named profile derives one deterministically
from its name, and an unknown id raises `ConfigError` naming it before any
resolution. A registered id may also carry historical variable names: `mcp`
honours `AXM_MCP_PORT` below the derived `AXM_NETWORK_MCP_PORT`; `orison_web`
carries none.

`profile` is the same keyword-only name the state accessors take, with the same
meaning: `None` means the active profile, so every existing call site resolves
unchanged, and a named one is answered through `profile_root_for` without
reading or writing `AXM_PROFILE`. `"production"` owns no root and therefore
returns the adopted number. The requested profile selects only the derived value
handed to `get_int` as its `default`, so a configured port still outranks it.

See [runtime settings](runtime-settings.md) for each wrapper and default.

## Execution policies

`ExecutionPolicyOverride`, `get_execution_policy(ticket_type)`,
`set_execution_policy(ticket_type, *, backend=None, model=None, analysis_enabled=None)`,
`delete_execution_policy(ticket_type)` and `list_execution_policies()`
are public. The [policy guide](../howto/execution-policies.md) specifies canonical
storage, complete replacement, environment pairing, tombstones and enumeration.

## NamespaceStore

`NamespaceStore()` is exported but lower-level than the validated resolver.
It has no path or profile constructor argument: methods consult the active
profile. Prefer the generic or policy helpers for application code.

| Method | Contract |
|---|---|
| `read(ns)` | Own scalar/array keys, excluding child tables; legacy fallback plus execution-policy compatibility overlay. |
| `read_exact(ns)` | Own section without execution overlay; still falls back to a legacy file if the section is empty. |
| `write(ns, key, value)` | Fold legacy, update one key, preserve children, replace the file. |
| `delete(ns, key)` | Fold legacy and remove a key; currently may erase child namespaces when modifying a parent. |
| `replace_section(ns, section)` | Replace own leaf keys while preserving child namespaces. |
| `namespaces()` | Sorted names from stored own-key tables and valid legacy filenames; no environment enumeration. |

The low-level store does not apply `validate_segment` to every method argument.
Do not pass untrusted namespace/key strings directly. Dict-valued TOML tables
are child namespaces rather than ordinary scalar settings. There is no
transaction, lock, multi-writer conflict detection or crash-durability guarantee.

## Tool boundaries

`ProfileIsolationTool` is root-exported; `ConfigDoctorTool` is imported from
`axm_config.tools`. Both implement the AXMTool protocol structurally and expose
`execute` returning `ToolResult`. See [CLI/tools](cli.md).
