# Architecture and persistence

## Responsibilities

| Module | Responsibility |
|---|---|
| `home` | Home creation/permissions and repository-path guard. |
| `profile` | Active profile selection and transport overlay. |
| `store` | TOML namespace reads, migration and file replacement. |
| `resolver` | Validated keys, precedence, model loading and execution policies. |
| `paths` | Typed runtime values, defaults and configured path guards. |
| `doctor` | Provenance report without returning values. |
| `isolation` | Candidate profile paths and lexical containment. |
| `tools` | AXMTool diagnostic boundaries. |
| `cli` | Cyclopts request/response commands calling the central functions. |

The SDK registry is `axm.tools`. No `axm.commands` registry or YAML hook
integration is required. The legacy YAML engine is decommissioned; the remaining
`protocols_dir` accessor is compatibility surface.

## One TOML file per profile

The store uses `~/.axm/config.toml` in production and
`~/.axm/profiles/<name>/config.toml` for a named profile. A dotted namespace
maps to nested TOML tables:

```toml
[research.demo]
dataset = "sample"
timeout = 30
```

Each namespace's own scalar/array keys are separate from child namespace tables.
`write` and `replace_section` preserve child tables. The generic resolver
validates names before passing them to the store.

## Lazy migration

The former `<store-directory>/<namespace>.toml` format remains readable.
If the current section has any own keys, a read returns that section as a whole;
it does **not** fill missing keys from the legacy file on each read.
Only when the section is empty/missing does the read fall back to legacy.

On a write or delete to that namespace, legacy keys are merged first and current
section keys win. The updated file is replaced, then the legacy file is removed.
A delete of an absent key can still perform this migration. Only the selected
profile's legacy files are considered. Unrelated namespaces are not all migrated
at once; policy canonicalization has its own [compatibility contract](../howto/execution-policies.md).

## Atomicity, durability and concurrency

A normal write loads the whole mapping, serializes it to a same-directory
temporary file and calls `os.replace`. The resulting file is chmod `0600` on
POSIX. The swap helper removes its staged temporary path even if replace/chmod
fails. The base home is tightened to `0700`; profile directories use the
process's normal mkdir permissions under that home.

This prevents readers observing a partly replaced file, but it is **not a
transaction across writers**. There is no lock or version check: two overlapping
read-modify-write operations can lose each other's updates, even when changing
different namespaces. Serialize all writers to the same profile file in the
owning application. There is no explicit file/directory `fsync`, so atomic
replacement is not a promise of persistence through power loss.

The commit and legacy unlink are separate operations. A failure after replacement
can leave changed contents despite an exception; chmod or legacy cleanup can
fail after the new file is visible. Temporary-file creation/write failures
before the swap helper are not covered by its cleanup guarantee.

## Current limits that affect data

- A missing, malformed or unreadable TOML file generally degrades to an empty
  mapping. A later write may replace that file with only the new known data.
  There is no automatic backup, recovery or corruption report.
- **Deleting an own key from a parent namespace can erase its child tables.**
  Unlike `write`/`replace_section`, `delete` does not reattach children.
  This also affects `set_(namespace, key, None)` and the CLI delete command.
  Avoid parent-key deletion in stores with descendants until the product defect
  is corrected; the dedicated policy deletion uses `replace_section`.
- The process environment selects the profile at each call; global environment
  changes are not safe per-thread profile contexts.
- `AXM_HOME`, typed accessor fallback and the isolation diagnostic do not share
  the store's home semantics. The [profile guide](../howto/profiles.md) details
  these boundaries rather than promising blanket isolation.

## Security and secrets boundary

This is plaintext **non-sensitive** configuration. Keep passwords, API keys and
tokens in axm-vault. Restrictive permissions do not turn TOML into a secret store.
The provenance doctor does not return values but does parse file contents.

The store resolves its home, refuses git-repository ancestry and enforces that
its resolved file paths stay below that home. This is containment under the base
home, not a symlink-proof boundary between sibling profiles; avoid treating
profile directory symlinks as isolation. `axm_home()` can create/chmod the
directory before the store rejects it. `resolve_safe` is a path check, not a
lock against filesystem changes between check and use.
