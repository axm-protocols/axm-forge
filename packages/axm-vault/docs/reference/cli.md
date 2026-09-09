# CLI Reference

axm-vault ships **two** command surfaces. `get` masks SECRET values by default;
`get --reveal` deliberately prints plaintext:

1. The standalone **`axm-vault`** console script (`[project.scripts]`), an
   interactive operator CLI built on [cyclopts](https://cyclopts.readthedocs.io).
2. The three **`axm.tools`** entry points (`vault_doctor`, `vault_set`,
   `vault_delete`), each reachable as an `axm <tool>` command, over MCP, and as
   a DAG node from a single declaration.

The CLI is a thin shell: it owns argument parsing and human-facing output but
delegates every operation to the central functions / tools, so no business
logic is duplicated across the CLI / MCP boundary.

## `axm-vault` commands

| Command | Purpose |
| -- | -- |
| `axm-vault setup [--only <group.name>]` | Interactively prompt for and store every storable credential (`getpass` for `SECRET`, `input` for `CONFIG`) |
| `axm-vault get <group> <name> [--reveal]` | Resolve a credential and print it, masking `SECRET` values as `********` unless `--reveal` |
| `axm-vault set <group> <name> [value]` | Store a credential by sensitivity (`SECRET`->keyring, `CONFIG`->config); echoes only the storage target |
| `axm-vault rotate <group> <name> [value] [--instance <id>]` | Rotate a `SECRET`, retaining the previous value as `{name}.prev` for one cycle |
| `axm-vault delete <group> <name> [--instance <id>]` | Remove a stored credential from the keyring; a safe no-op when it is already absent (resolves the spec via the catalog first) |
| `axm-vault doctor [--package <pkg>] [--instance <id>]` | Print each credential's provenance (`layer` + `present`) — value-free. Appends a `keyring:unavailable` marker on any `SECRET` row whose keyring backend is unreachable |
| `axm-vault path` | Print the resolved `~/.axm` home directory used for file-backed config |

There is deliberately **no** `import` command — a bulk credential importer is
deferred.

```bash
# One-time interactive provisioning (refuses to run without a TTY)
axm-vault setup

# Resolve a credential — SECRET values are masked unless --reveal
axm-vault get broker api_key            # -> ********
axm-vault get broker api_key --reveal   # -> s3cr3t

# Store / rotate a secret (the value is never echoed back)
axm-vault set broker api_key s3cr3t
axm-vault rotate broker api_key new-s3cr3t

# Remove a stored secret — idempotent: a second delete is a safe no-op
axm-vault delete broker api_key   # -> deleted keyring:broker.api_key

# Which layer answers each credential, and is it present? (never the value)
axm-vault doctor
# svc.token	env	present
# svc.secret	missing	-	keyring:unavailable   # keyring backend unreachable
```

The `doctor` output is one tab-separated row per credential: `group.name`,
the winning `layer` (or `missing`), and `present`/`-`. When the OS keyring
backend is unavailable on the host, every keyring-eligible (`SECRET`) row gains
a trailing `keyring:unavailable` column so the outage is visible instead of
silently reading as a plain `missing`.

### `setup` — interactive provisioning

`setup` is an interactive provisioning driver (`run_setup`) that returns after
walking the catalog. It:

- **refuses to run without a TTY** — a non-interactive invocation prints to
  stderr and exits `1`, so credentials are never written silently;
- **skips `NONSENSITIVE` specs** — they are environment-only; storing them
  would create a second, stale source of truth;
- **is idempotent** — a blank answer keeps any existing value, so a re-run
  can preserve existing values or replace them with a nonblank answer (the prompt advertises `[keep]` when a
  value already exists);
- routes `SECRET` -> keyring only (presence is derived by probing the keyring,
  never recorded as a separate marker) and `CONFIG` -> `axm-config`.

## `axm.tools` (MCP)

All three tools are deterministic `axm.tools.base.AXMTool` implementations, so a
single entry-point declaration exposes each over MCP, the `axm` CLI and as a
DAG node. Successful tool results report provenance or targets, not stored values.

| Command | Purpose |
| -- | -- |
| `axm vault_doctor [--package <pkg>] [--instance <id>]` | Report each credential's provenance (`layer` + `present`) — value-free |
| `axm vault_set --group <id> --name <spec> --value <v> [--instance <id>]` | Store a credential by sensitivity (SECRET->keyring, CONFIG->config); reports only the target |
| `axm vault_delete --group <id> --name <spec> [--instance <id>]` | Remove a stored credential from the keyring; reports only the deletion target, a safe no-op when absent |

```bash
# Which layer answers each credential, and is it present? (never the value)
axm vault_doctor

# Store a secret into the OS keyring (value is never echoed back)
axm vault_set --group broker --name api_key --value s3cr3t

# Remove a stored secret from the keyring (idempotent, value-free)
axm vault_delete --group broker --name api_key
```

See [Doctor & Tools](doctor.md) for the full parameter and routing tables.

## Python API

Rendered API reference is available under [Python API](api/index.md).

## Operational limits

- Omit `value` from standalone `set` and `rotate` to use hidden `getpass` input. Supplying a real secret as an argument exposes it to shell history and process arguments. `vault_set` requires a value and has no hidden-input mode.
- `get`, standalone `set`, and `setup` have no `instance` option. Use the Python resolver and `vault_set --instance` for named keyring instances. `setup` does not enumerate instances or authentication sessions.
- `setup --only` accepts `group.name` or a bare name; a bare name may match several groups and an unmatched filter does nothing. Blank input never creates a missing required value, so completion does not prove provisioning completeness.
- `delete` removes only the keyring slot, even for a CONFIG spec, and leaves `.prev`, file and environment sources intact. Resolution can still succeed after deletion.
- Tool failures become `ToolResult(success=False, error=str(exc))`. Standalone `set`, `rotate` and `delete` exit 1 for reported failures; `get` handles unknown/missing credentials but other I/O errors may propagate. These messages are not a universal redaction boundary.
