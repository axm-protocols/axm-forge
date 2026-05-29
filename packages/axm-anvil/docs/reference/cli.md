# CLI Reference

## Commands

### `axm-anvil move`

Move top-level symbols (classes, functions, constants) between Python
files atomically. Wraps the [`MoveTool`](#movetool) MCP tool.

```bash
axm-anvil move <from_file> <to_file> <symbols> [--dry-run] [--check] [--path <root>] [--shared-helpers <strategy>] [--reexport] [--rename '<json>'] [--insert-after <symbol>] [--no-include-helpers] [--side-effect-decorators '<csv>']
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
| `--rename` | JSON object string mapping old symbol names to new ones (e.g. `'{"OldName": "NewName"}'`). Renames moved definitions and rewrites all caller references to the new name. Incompatible with `--reexport` |
| `--insert-after` | Name of an existing top-level symbol in the target module; moved blocks are spliced immediately after it. Omitted (default) appends the blocks at the end of the target; naming an absent symbol appends at the end and records a warning on `MovePlan.warnings`. Imports and constants keep their historical placement regardless |
| `--include-helpers` / `--no-include-helpers` | Whether to copy transitively-referenced local helpers and constants into the target. `--include-helpers` (default) preserves the historical copy behaviour. `--no-include-helpers` leaves the moved code referencing those helpers without copying them, short-circuits the `--shared-helpers` classification, and records a `include_helpers=False: not copied into target: <names>` warning on `MovePlan.warnings`. Imports required by the moved code are always copied regardless |
| `--side-effect-decorators` | Comma-separated extra side-effect decorator dotted-names (e.g. `'mylib.register'`) that **extend** the built-in [`SIDE_EFFECT_DECORATORS`](#side_effect_decorators) whitelist. When a moved symbol carries a matching decorator, a non-blocking warning is recorded on `MovePlan.warnings`; the move always proceeds |

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

### `SIDE_EFFECT_DECORATORS`

::: axm_anvil.core.move.SIDE_EFFECT_DECORATORS

The default whitelist of decorator dotted-names whose primary purpose is to
register the decorated symbol with an external registry as an import-time
side effect (e.g. `app.route`, `pytest.fixture` / bare `fixture`,
`celery.task`, `click.command`). When a moved `FunctionDef`/`ClassDef`
carries a matching decorator — in bare (`@fixture`), dotted
(`@pytest.fixture`), or call (`@app.route("/x")`) form — `move_symbols`
records a non-blocking warning on `MovePlan.warnings` noting that
registration may not run in the new module. The move is never blocked.
Callers extend the whitelist via the `side_effect_decorators` parameter of
[`move_symbols`](#move_symbols) (or `--side-effect-decorators` on the CLI);
supplied entries are unioned with these defaults.

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
