# How-To Guides

Task-oriented recipes for common `axm-anvil move` workflows. The dedicated
`axm-anvil` CLI exposes a single `move` command, which accepts positional
(`FROM TO SYMBOLS`) or flag (`--from-file/--to-file/--symbols`) form; see the
[CLI Reference](../reference/cli.md) for the full option list. `rename` and
`extract` are available via MCP (`anvil_rename`, `anvil_extract`) and the
`axm` dispatcher — see [Use via MCP](mcp.md).

## Preview a move before touching the disk

```bash
axm-anvil move src/mylib/models.py src/mylib/services.py UserService --dry-run
```

The printed plan lists moved symbols, copied imports/constants, caller rewrites,
and any warnings — nothing is written.

## Rename a symbol while moving it

```bash
axm-anvil move src/mylib/models.py src/mylib/services.py \
    UserService --rename '{"UserService": "AccountService"}'
```

The definition, all references, the `__all__` entry, and string forward-references
(`x: "UserService"`) are all rewritten to the new name. Incompatible with
`--reexport`.

## Control where the moved code lands

```bash
axm-anvil move src/mylib/a.py src/mylib/b.py Widget --insert-after existing_fn
```

Moved blocks are spliced immediately after `existing_fn` in the target. Without
`--insert-after` they are appended at the end; naming an absent symbol appends at
the end and records a warning.

## Move without copying local helpers

```bash
axm-anvil move src/mylib/a.py src/mylib/b.py Widget --no-include-helpers
```

Transitively-referenced local helpers and constants are left behind (imports the
moved code needs are still copied). A `include_helpers=False: not copied into
target: <names>` warning lists what was skipped.

## Migrate gradually with a re-export shim

```bash
axm-anvil move src/mylib/a.py src/mylib/b.py Widget --reexport
```

Callers are left untouched; a `from b import Widget  # re-export for backwards
compat` line is injected into the source so existing imports keep working.

## Catch import cycles before writing

```bash
axm-anvil move src/mylib/a.py src/mylib/b.py Widget --check
```

Simulates the move (including caller rewrites) and fails with `ImportCycleError`
if it would introduce a *new* import cycle. Pre-existing cycles are ignored.
