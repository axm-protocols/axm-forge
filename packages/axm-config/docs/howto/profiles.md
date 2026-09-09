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

`axm_home()` creates/tightens `~/.axm` to mode `0700` on POSIX.
Path helpers and store reads can call it. The named profile directory is created
on first write, with normal `mkdir`/umask permissions under that private parent.
`axm-config path` prints the base home, not the selected config file.

## Propagate the selection

`profile_env()` returns only `{"AXM_PROFILE": current_profile()}`.
Merge that overlay into a child process's environment; it is not a complete
environment and does not carry other AXM overrides. Avoid changing process-global
`os.environ` concurrently to switch profiles: the selection is not a per-request
or thread-local context.

## Interpret the diagnostic correctly

```bash
AXM_HOME=/tmp/axm-profile-example axm profile_isolation --profile scratch
```

This calculation creates no directories. It constructs paths for tickets,
warden socket/log, sessions, quality and protocols under
`AXM_HOME/profiles/scratch` (or `~/.axm/profiles/scratch` without `AXM_HOME`).

It does **not** consult configured path overrides or prove what consumers use.
Even `profile_isolation("production")` constructs `profiles/production`,
whereas the actual production resolver has no profile root.
`is_isolated(root, paths)` is a lexical `Path.is_relative_to` check; it does
not resolve symlinks or `..` segments. Supply normalized paths when using it
directly, and do not treat its result as a filesystem security audit.

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
