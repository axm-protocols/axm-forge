# CLI Reference

## Commands

### `axm-anvil move`

Move top-level symbols (classes, functions, constants) between Python
files atomically. Wraps the [`MoveTool`](#movetool) MCP tool.

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
| `--rename` | JSON object string mapping old symbol names to new ones (e.g. `'{"OldName": "NewName"}'`). Renames moved definitions and rewrites all caller references to the new name. Incompatible with `--reexport` |
| `--insert-after` | Name of an existing top-level symbol in the target module; moved blocks are spliced immediately after it. Omitted (default) appends the blocks at the end of the target; naming an absent symbol appends at the end and records a warning on `MovePlan.warnings`. Imports and constants keep their usual end-of-file placement regardless |
| `--include-helpers` / `--no-include-helpers` | Whether to copy transitively-referenced local helpers and constants into the target. `--include-helpers` (default) copies private helper symbols alongside the moved symbol. `--no-include-helpers` leaves the moved code referencing those helpers without copying them, short-circuits the `--shared-helpers` classification, and records a `include_helpers=False: not copied into target: <names>` warning on `MovePlan.warnings`. Imports required by the moved code are always copied regardless |
| `--side-effect-decorators` | Comma-separated extra side-effect decorator dotted-names (e.g. `'mylib.register'`) that **extend** the built-in `SIDE_EFFECT_DECORATORS` whitelist (see [Python API](#python-api)). When a moved symbol carries a matching decorator, a non-blocking warning is recorded on `MovePlan.warnings`; the move always proceeds |

## MCP Tools

### `MoveTool`

Registered as `anvil_move` via the `axm.tools` entry point. Accepts the
same fields as the CLI and returns a `ToolResult` with the move plan
(moved symbols, copied imports/constants, warnings).

::: axm_anvil.tools.move.MoveTool

### `ExtractTool`

Registered as `anvil_extract` via the `axm.tools` entry point (reachable as
`axm anvil_extract` on the CLI and via MCP). Extracts top-level symbols from
`from_file` into a **new** `to_file` (created on disk, parent directories
included), copying the same transitive dependencies (imports, local
helpers, constants) as `anvil_move` and rewriting every cross-file caller
(`from old import X` to `from new import X`). It is a thin specialisation of
[`MoveTool`](#movetool) where the target module does not yet exist:
extracting into a *pre-existing* module that already defines one of the
requested symbols fails with `success=False` (no silent overwrite). With
`dry_run=True` the plan is computed without leaving any file on disk.
`reexport` and `check` are intentionally not exposed (meaningless against a
freshly created module). The returned `ToolResult` carries the same shape
as `anvil_move` (`moved`, `dependencies_copied`, `callers_updated`,
`warnings`, `shared_helpers_detected`, `files_modified`).

::: axm_anvil.tools.extract.ExtractTool

### `RenameTool`

Registered as `anvil_rename` via the `axm.tools` entry point (so it is
reachable as `axm anvil_rename` on the CLI and via MCP). Renames top-level
symbols **in place** — definition and internal usages — and rewrites every
cross-file caller (`from mod import Old` import alias and usages). Pass a
mono-symbol `old`/`new` pair, or a `mapping` JSON object (e.g.
`'{"OldName": "NewName"}'`) for batch renames. `dry_run` previews the plan
without writing; `strict` turns an absent symbol into a `success=False`
result instead of a skipped-with-warning. `reexport` is intentionally not
exposed (incompatible with rename). The returned `ToolResult` carries
`renamed`, `callers_updated`, `warnings`, and `files_modified`.

::: axm_anvil.tools.rename.RenameTool

## Python API

The full Python API — every public function, model, and exception with its
signature and docstring — is rendered from source under
**[Python API](api/)**. This section captures only the cross-cutting
semantics that span several symbols.

**`extract_symbols`** — thin adapter over `move_symbols` for the *extract*
case: the target module is **created** rather than amended. When
`target_path` does not exist it is scaffolded as an empty module so the move
pipeline can fill it; a pre-existing target already defining a requested
symbol raises `SymbolAlreadyExistsError` (no silent overwrite). A
`dry_run=True` call removes any scaffolded target — and any directories it
created — before returning, leaving disk state byte-identical. All other
parameters mirror `move_symbols` and are forwarded verbatim; `reexport` and
`check` are not exposed.

**`rename_symbols`** — renames the top-level symbols in `mapping` in place
in `file` and rewrites every cross-file caller discovered under the
workspace root. A rename onto a name that already exists in the module is
refused with `SymbolAlreadyExistsError` (no duplicate definition). Caller
rewriting is pattern-based on the import statement; shadowing, alias chains,
and re-exports/star imports are deferred to a later tier (see the function
and module docstrings).

**`SIDE_EFFECT_DECORATORS`** — the default whitelist of decorator
dotted-names whose primary purpose is to register the decorated symbol with
an external registry as an import-time side effect (e.g. `app.route`,
`pytest.fixture` / bare `fixture`, `celery.task`, `click.command`). When a
moved `FunctionDef`/`ClassDef` carries a matching decorator — in bare
(`@fixture`), dotted (`@pytest.fixture`), or call (`@app.route("/x")`) form
— `move_symbols` records a non-blocking warning on `MovePlan.warnings`. The
move is never blocked. Callers extend the whitelist via the
`side_effect_decorators` parameter of `move_symbols` (or
`--side-effect-decorators` on the CLI).

**`SymbolNotFoundError`** — a requested name absent from the source module's
**top-level** symbols is **skipped** by default: `move_symbols` drops it and
records a `skipped '<name>': not a top-level symbol in source` entry on
`MovePlan.warnings`. The CLI and the `anvil_move` MCP tool surface that
warning and still exit successfully. Pass `strict=True` (or `--strict`) to
raise on the first absent name instead.

**`ImportCycleError`** — raised by `move_symbols` when the requested move
(or its caller rewrites) would introduce a *new* import cycle. Pre-existing
cycles are ignored. Raised when `check=True` or during a normal
(non-dry-run) write; a pure `dry_run=True` call skips the raise to preserve
the preview contract.
