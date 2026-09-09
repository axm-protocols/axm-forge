# CLI Reference

## Commands

### `axm-anvil move`

Move top-level symbols (classes, functions, constants) between Python
files through a validated batch plus optional Ruff post-processing. Wraps the [`MoveTool`](api/index.md#axm_anvil.MoveTool) MCP tool.

```bash
axm-anvil move <from_file> <to_file> <symbols> [--dry-run] [--check] [--strict] [--path <root>] [--shared-helpers <strategy>] [--reexport] [--rename '<json>'] [--insert-after <symbol>] [--no-include-helpers] [--side-effect-decorators '<csv>']
```

| Argument | Description |
|---|---|
| `from_file` | Source Python file path |
| `to_file` | Target Python file path |
| `symbols` | Comma-separated symbol names to move |
| `--dry-run` | Preview the move without writing files |
| `--check` | Simulate the move, including import-cycle detection, without writing. Fails with `ImportCycleError` if the move would introduce a new cycle |
| `--strict` | Fail (non-zero exit) on a requested symbol that is absent from the source module instead of skipping it with a warning. Default (`--no-strict`) skips an absent symbol and records a warning |
| `--path` | Workspace root (default: `.`) |
| `--shared-helpers` | Strategy when a helper is used by both moved and remaining symbols: `duplicate` (default, copies the helper and emits a warning) or `error` (abort with `SharedHelpersError`) |
| `--reexport` | Leave callers untouched; inject `from new_module import <Symbol>  # re-export for backwards compat` into the source module for gradual migration |
| `--rename` | JSON object string mapping old symbol names to new ones (e.g. `'{"OldName": "NewName"}'`). Renames moved definitions and rewrites supported caller references to the new name. Incompatible with `--reexport` |
| `--insert-after` | Name of an existing top-level symbol in the target module; moved blocks are spliced immediately after it. Omitted (default) appends the blocks at the end of the target; naming an absent symbol appends at the end and records a warning on `MovePlan.warnings`. Imports and constants keep their usual end-of-file placement regardless |
| `--include-helpers` / `--no-include-helpers` | Whether to copy transitively-referenced local helpers and constants into the target. `--include-helpers` (default) copies private helper symbols alongside the moved symbol. `--no-include-helpers` leaves the moved code referencing those helpers without copying them, short-circuits the `--shared-helpers` classification, and records a `include_helpers=False: not copied into target: <names>` warning on `MovePlan.warnings`. Imports required by the moved code are always copied regardless |
| `--side-effect-decorators` | Comma-separated extra side-effect decorator dotted-names (e.g. `'mylib.register'`) that **extend** the built-in `SIDE_EFFECT_DECORATORS` whitelist (an internal constant; see [limits](../explanation/limits.md)). When a moved symbol carries a matching decorator, a non-blocking warning is recorded on `MovePlan.warnings`; the warning alone does not block the move |

## Generic AXM commands

`axm anvil_move`, `axm anvil_rename` and `axm anvil_extract` use installed
`axm.tools` entry points. Their flags derive from `execute`; use `--help` on
that command for the installed schema. The dedicated `axm-anvil` binary has
**only move**. See [MCP/dispatcher examples](../howto/mcp.md).

```bash
axm anvil_move --help
axm anvil_rename --help
axm anvil_extract --help
```

The generic CLI supports `--json-output` (data only); the dedicated move command emits
compact text and has no JSON option. Tool failures exit non-zero with stderr;
successful no-ops and warning-bearing results still exit zero.

## Python API

See [root exports and signatures](api/index.md) and [operation contracts](contracts.md)
for the complete result fields, path semantics, errors and defaults. The
[write guarantees](../explanation/limits.md) apply to both interfaces. Preview
plans list potential files, not evidence of writes, and extract's file list
omits callers. Unsupported kwargs may be ignored by tool wrappers.
