# Scaffold protocol packages and units

Use the Python `protocols` profile. Declaration requests target an existing
package with `pyproject.toml`; create that package first if necessary.

## Create a protocol package

A standalone package or workspace member can declare the Python protocol
profile while it is created:

```bash
axm init_scaffold protocols-dev \
  --profile protocols --domain dev \
  --protocols '[]' \
  --org myorg --author "Your Name" --email "you@example.com"
```

This writes `[tool.axm-init.protocols]` into the generated package metadata.
The structured result reports `profile`, the derived `distribution`, the
creation `mode` (`standalone` or `member`), and the package `root`.

To inspect a protocol unit without writing files or metadata, select
`protocol_unit`, pass action-only payloads as JSON, and enable preview. Use
`protocol` for the same preview path when targeting an existing unit:

```bash
axm init_scaffold protocols-dev --kind protocol_unit \
  --profile protocols --domain dev --unit work --preview \
  --protocols '[{"action":"create","contracts":[{"name":"brief"}],
    "nodes":[{"name":"author","contract":"brief"}]}]' \
  --org myorg --author "Your Name" --email "you@example.com" \
  --json-output
```

Preview and application use the same planner. Its structured payload
sets `preview=true`, reports qualified graph names such as
`dev.work.create`, and partitions relative paths into `created`, `updated`,
`unchanged`, and `conflicts`. The request-level domain and unit are injected
into every payload before the strict internal declaration is validated.
Option validation happens before target filesystem mutation:
a protocol request without a profile, an empty declaration list when `--unit` or `--preview` is supplied, a
non-Python protocol profile, or declarations without `--unit` fails without
changing the target.


## Apply the reviewed declarations

Repeat the preview command with exactly the same declaration JSON and omit
`--preview` (or pass `--no-preview`). The orchestrator performs a complete
path/conflict preflight, then writes the planned files and merged metadata.
The resulting `preview` field is false.

The current human message can still say `Protocol scaffold preview` during
application; inspect the structured `preview` field and the path lists.
On a caught write failure, the implementation attempts to restore prior
files and metadata and remove new files. This is an in-process rollback,
not durable crash recovery or concurrency serialization.

See [declarations and result fields](../reference/protocol-scaffold.md).
