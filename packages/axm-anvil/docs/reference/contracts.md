# Operation contracts

All operations target Python **top-level** classes, functions and assignments. They do not rename a method independently or prove runtime equivalence. Use an explicit workspace root that contains source, destination and callers.

## Choosing an operation

| Operation | Destination | Preview | Cycle enforcement |
|---|---|---|---|
| `anvil_move` / `move_symbols` | Existing readable Python file | `dry_run=True`; `check=True` also previews | Normal apply and `check=True`; plain dry-run does not raise on a detected new cycle |
| `anvil_extract` / `extract_symbols` | Creates missing file and parent directories; also accepts an existing target without a requested-name collision | Creates then cleans up a temporary scaffold if needed | Normal apply uses the move pipeline; no `check` option |
| `anvil_rename` / `rename_symbols` | Same defining module | `dry_run=True` | No move-cycle check |

Extraction does not create package `__init__.py` files. Choose an importable destination. An existing definition with a requested name blocks move/extract; rename also rejects a destination name already defined. `strict=False` skips absent names with warnings. An all-absent move or rename is a successful no-op; an all-absent **extract apply can leave an empty new target**.

## Tool inputs

Tools resolve relative file paths against `path` (default `.`); absolute paths remain absolute. `path` is a discovery root, not a sandbox: move can re-anchor its write root to a common ancestor for endpoints outside it. Core `move_symbols` and `extract_symbols` instead consume file paths relative to the process working directory; `workspace_root` controls discovery/writes, not file-path resolution.

Move/extract accept CSV `symbols`, JSON-string `rename`, `shared_helpers="duplicate"`, `shared_helpers_module=None`, `strict=False`, `insert_after=None`, `include_helpers=True`, `side_effect_decorators=None`. Only move accepts `reexport=False` and `check=False`. Rename accepts `file`, `old` and `new`, or JSON-string `mapping`; mapping takes precedence and its keys/values are converted to strings. Use valid, unique Python identifiers.

`shared_helpers="error"` rejects shared helpers. `"extract"` and **any non-None** `shared_helpers_module` raise `NotImplementedError`: the parameter exists but the strategy is not implemented. `reexport=True` is incompatible with a non-None rename mapping, including `{}`. Unsupported kwargs are accepted by the tool wrappers but ignored; do not infer support from a successful call.

## ToolResult and plans

Check `ToolResult.success` before reading `data`. Failures normally carry `error`; warnings do not set success to false. The generic AXM CLI prints `data` with `--json-output`, rather than the full ToolResult envelope. Compact text is a summary, not a diff.

| Data field | Move / extract | Rename |
|---|---|---|
| `moved` | List of `{"symbol": "OriginalName"}`; names precede in-flight renaming | Absent |
| `renamed` | Absent | List of `{"old": "Old", "new": "New"}` |
| `dependencies_copied` | `imports` and `constants` lists | Absent |
| `callers_updated` | Records with `file`, `line`, `old`, `new` | Same keys, `line=0`, old/new hold the same module name |
| `warnings` | List of messages | List of messages |
| `shared_helpers_detected` | Records: `name`, `used_by_moved`, `used_by_remaining` | Absent |
| `files_modified` | Source and target, plus caller records **for move only** | Defining module plus caller paths |

`files_modified` is populated during preview too, so it is not proof of a write. Move may mix absolute endpoint paths with relative caller paths and repeat a caller. Extract currently omits rewritten callers from this field: inspect `callers_updated` and the actual diff as well. Move adds `reexport: true` or `check: true` only when enabled.

The Python `MovePlan` dataclass contains `source_text_new`, `target_text_new`, `moved_names`, `imports_added`, `constants_added`, `warnings`, `shared_helpers_detected` and `callers_updated`. It has **no** `files_modified`. Texts describe the plan **before Ruff post-processing**. `RenamePlan` contains `source_text_new`, `renamed` (a dict), `callers_updated`, `warnings` and `files_modified`. Neither is a Pydantic model; neither is a reusable apply token.

## Errors

Core functions raise exceptions. The tools convert exceptions from the core to failure results; argument normalization occurs before the move/extract try block, so direct Python callers should still handle exceptions. The dedicated CLI exits 1 on a failed ToolResult, prints the error to stderr, and prints successful text to stdout.

| Root-exported exception | Meaning |
|---|---|
| `SymbolNotFoundError` | Missing requested top-level symbol with strict mode |
| `SymbolAlreadyExistsError` | Requested or renamed destination collides |
| `ImportCycleError` | A newly introduced import cycle is rejected |
| `SharedHelpersError` | Shared helper under the error strategy |
| `MoveValidationError` | Invalid transformed Python |
| `MovePathError` | Source and target have no usable common base |
| `OverloadPartialMoveError` | Overload-group error type; ordinary moves expand companions together |

These types are part of the exported API, not a claim that every path uses each type. Missing files can raise `FileNotFoundError`; unsupported options can raise `ValueError` or `NotImplementedError`; a failed batch raises `RuntimeError`. See [write and semantic limits](../explanation/limits.md) before interpreting success.
