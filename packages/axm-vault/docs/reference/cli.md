# CLI Reference

axm-vault ships **two** command surfaces, both upholding the never-leak
invariant — no command ever prints a `SECRET` value:

1. The standalone **`axm-vault`** console script (`[project.scripts]`), an
   interactive operator CLI built on [cyclopts](https://cyclopts.readthedocs.io).
2. The two **`axm.tools`** entry points (`vault_doctor`, `vault_set`), each
   reachable as an `axm <tool>` command, over MCP, and as a DAG node from a
   single declaration.

The CLI is a thin shell: it owns argument parsing and human-facing output but
delegates every operation to the central functions / tools, so no business
logic is duplicated across the CLI / MCP boundary.

## `axm-vault` commands

| Command | Purpose |
| -- | -- |
| `axm-vault setup [--only <group.name>]` | Interactively prompt for and store every storable credential (`getpass` for `SECRET`, `input` for `CONFIG`) |
| `axm-vault get <group> <name> [--reveal]` | Resolve a credential and print it, masking `SECRET` values as `********` unless `--reveal` |
| `axm-vault set <group> <name> <value>` | Store a credential by sensitivity (`SECRET`->keyring, `CONFIG`->config); echoes only the storage target |
| `axm-vault rotate <group> <name> <value> [--instance <id>]` | Rotate a `SECRET`, retaining the previous value as `{name}.prev` for one cycle |
| `axm-vault doctor [--package <pkg>] [--instance <id>]` | Print each credential's provenance (`layer` + `present`) — value-free |
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

# Which layer answers each credential, and is it present? (never the value)
axm-vault doctor
```

### `setup` — interactive provisioning

`setup` is the only genuine *process-lifecycle* command: it reads from a TTY
and blocks on operator input, which is why it lives as a plain function
(`run_setup`) behind the CLI rather than as an `AXMTool`. It:

- **refuses to run without a TTY** — a non-interactive invocation prints to
  stderr and exits `1`, so credentials are never written silently;
- **skips `NONSENSITIVE` specs** — they are environment-only; storing them
  would create a second, stale source of truth;
- **is idempotent** — a blank answer keeps any existing value, so a re-run
  only fills in what is still missing (the prompt advertises `[keep]` when a
  value already exists);
- routes `SECRET` -> keyring (with a value-free presence sentinel in
  `axm-config`) and `CONFIG` -> `axm-config`.

## `axm.tools` (MCP)

Both tools are deterministic `axm.tools.base.AXMTool` implementations, so a
single entry-point declaration exposes each over MCP, the `axm` CLI and as a
DAG node. Neither command ever prints a `SECRET` value.

| Command | Purpose |
| -- | -- |
| `axm vault_doctor [--package <pkg>] [--instance <id>]` | Report each credential's provenance (`layer` + `present`) — value-free |
| `axm vault_set --group <id> --name <spec> --value <v> [--instance <id>]` | Store a credential by sensitivity (SECRET->keyring, CONFIG->config); reports only the target |

```bash
# Which layer answers each credential, and is it present? (never the value)
axm vault_doctor

# Store a secret into the OS keyring (value is never echoed back)
axm vault_set --group broker --name api_key --value s3cr3t
```

See [Doctor & Tools](doctor.md) for the full parameter and routing tables.

## Python API

Auto-generated API reference is available under [Python API](api/).
