# CLI Reference

## Commands

### `axm-anvil move`

Move top-level symbols (classes, functions, constants) between Python
files atomically. Wraps the [`MoveTool`](#movetool) MCP tool.

```bash
axm-anvil move <from_file> <to_file> <symbols> [--dry-run] [--check] [--path <root>] [--shared-helpers <strategy>] [--reexport]
```

| Argument | Description |
|---|---|
| `from_file` | Source Python file path |
| `to_file` | Target Python file path |
| `symbols` | Comma-separated symbol names to move |
| `--dry-run` | Preview the move without writing files |
| `--check` | Simulate the move, including import-cycle detection, without writing. Fails with `ImportCycleError` if the move would introduce a new cycle |
| `--path` | Workspace root (default: `.`) |
| `--shared-helpers` | Strategy when a helper is used by both moved and remaining symbols: `duplicate` (default, copies the helper and emits a warning) or `error` (abort with `SharedHelpersError`) |
| `--reexport` | Leave callers untouched; inject `from new_module import <Symbol>  # re-export for backwards compat` into the source module for gradual migration |

## MCP Tools

### `MoveTool`

Registered as `ast_move` via the `axm.tools` entry point. Accepts the
same fields as the CLI and returns a `ToolResult` with the move plan
(moved symbols, copied imports/constants, warnings).

::: axm_anvil.tools.move.MoveTool

## Python API

### `move_symbols`

::: axm_anvil.core.move.move_symbols

### `MovePlan`

::: axm_anvil.core.plan.MovePlan

### `CallerRewrite`

::: axm_anvil.core.callers.CallerRewrite

One entry per caller import line rewritten by `move_symbols`. Populated
into `MovePlan.callers_updated` so downstream tooling (CLI output, MCP
response) can report every `from old_module import …` line that was
redirected to the new module.

### `SharedHelpersError`

::: axm_anvil.core.plan.SharedHelpersError

Raised by [`move_symbols`](#move_symbols) when `shared_helpers="error"`
and at least one helper is transitively referenced by both a moved block
and a remaining source symbol. The exception's `shared_helpers` attribute
lists the offending helper names.

### `ImportCycleError`

::: axm_anvil.core.plan.ImportCycleError

Raised by [`move_symbols`](#move_symbols) when the requested move (or the
associated caller rewrites) would introduce a *new* import cycle into the
containing package. Pre-existing cycles are ignored. The exception is
raised when `check=True` or during a normal (non-dry-run) write. Pure
`dry_run=True` calls skip the raise to preserve the existing preview
contract.

### `SymbolNotFoundError`

::: axm_anvil.core.plan.SymbolNotFoundError

A requested name that is absent from the source module's **top-level**
symbols (for example a `test_basic` method declared inside a `Test*`
class, or a name that simply does not exist) is **skipped** by default:
[`move_symbols`](#move_symbols) drops it from the move and records a
`skipped '<name>': not a top-level symbol in source` entry on
`MovePlan.warnings`. The CLI and the `ast_move` MCP tool surface that
warning and still exit successfully. Pass `strict=True` to restore the
legacy behaviour of raising `SymbolNotFoundError` on the first absent
name. Names that *are* present continue to move exactly as before.

Auto-generated API reference is available under [Python API](api/).
