# Batch operations

## Tool arguments

| Parameter | Default | Meaning |
|---|---|---|
| `path` | `"."` | Existing project root |
| `operations` | `None` | Nonempty list of operation dictionaries |
| `lint` | `True` | Run Ruff fix and format on touched Python files |
| `lint_diff` | `True` | Include detected post-lint mutations |
| `lint_diff_max_ratio` | `0.5` | Diff-size / post-lint-file-size threshold |

`batch_edit_check` takes only `path` and `operations`.
`batch_rollback` takes `path` and the full `checkpoint` string.
Use exact parameter names: extra tool kwargs may be ignored rather than rejected.

## Operations

| `op` | Required payload | Target |
|---|---|---|
| `replace` | `file`, `edits` with `old` and `new` | Existing text file |
| `create` | `file`, `content` | Absent path; parents created |
| `delete` | `file` | Existing file |
| `rewrite` | `file`, `content`, `checksum` | Existing regular nonbinary file |

The tool accepts `expected_checksum` as an alias for `checksum` only in
`batch_edit`; the check tool expects `checksum`.
The typed `RewriteOp` model uses `expected_checksum`.
Do not combine different operation kinds on one path: this is not a sequential
file-operation script. Replace edits are grouped and applied before creates,
deletes and rewrites, rather than replayed in raw list order.

### Replace anchors

```json
{
  "op": "replace",
  "file": "settings.txt",
  "edits": [
    {"line": 1, "old": "mode = draft", "new": "mode = ready"}
  ]
}
```

Each optional `line` is a 1-based hint in the original file.
All edits for a file are resolved before apply, then spliced bottom to top.
`old` must be nonempty and match complete lines, not a substring.
An empty `new` deletes the matched block without leaving a blank line.

For tool calls, copy indentation, omit trailing newlines from `old` and
`new`, and avoid triple quotes in `old`. Use a unique, small anchor.
The engine can recover shifted lines, normalized quotes and dedented matches;
these fallbacks are not semantic code analysis. Overlapping edits and unresolved
ambiguous anchors are rejected. A preflight warning about ambiguity does not
mean engine validation will accept it.

Replacements preserve detected LF or CRLF style. New replacement content
receives a terminating newline when nonempty. Use rewrite when exact whole-file
UTF-8 content is important, including a missing final newline.

### Create, delete and rewrite

```json
{"op": "create", "file": "notes/new.txt", "content": "Ready.\n"}
```

Create refuses an existing path; there is no `overwrite` flag.

```json
{"op": "delete", "file": "notes/obsolete.txt"}
```

Delete has no expected-content or digest condition. Re-read and coordinate
writers before deleting a path.

For rewrite, use the [digest workflow](../howto/rewrite.md).
The payload's content is UTF-8 text. Checksum refusal prevents overwriting an
already-stale read at validation time; it does not lock out subsequent writers.

## Preflight result

When the check runs, it returns `success=True` even for blocking diagnostics:

```json
{
  "ok": true,
  "diagnostics": [],
  "blocking": false,
  "error_count": 0,
  "warning_count": 0
}
```

The object above is a clean preflight result. `ok` is precisely
`not diagnostics`. Each diagnostic has `op_index`,
`file`, `severity`, `code`, `message`, `hint`, and optional
`edit_index` / `anchor_excerpt`. Indices are zero-based.
Diagnostics are ordered by operation, then rule family.
`blocking` means at least one error; warnings alone set `ok=False`.

A check is a preflight rule report, not a full dry run of the engine. It does
not execute writes, simulate an entire batch, or guarantee later validation.
In particular, engine-only target checks and overlapping/conflicting operations
can still fail. The apply tool repeats preflight, then parses and validates.

## Apply result

Successful structured data contains `applied`, `summary`, `details`,
`preflight` and `checkpoint`.
`summary` counts modified/created/deleted files and includes `rewritten`
only when rewrites exist. `applied` counts individual replace edits plus
create/delete/rewrite operations, not simply the number of files.

Nested `preflight` contains `diagnostics`, `errors`, `warnings` and
`blocking`. A blocking preflight returns failure without a checkpoint.
Apply failures can carry a checkpoint. See [recovery](../howto/rollback.md)
for the distinction between the tool payload and root `BatchResult`.

## Post-edit Ruff

With `lint=True`, changed Python files are checked, fixed with
`uv run ruff check --fix --exit-zero --extend-select I`, then formatted,
then checked again. This invokes `uv` in the project root and can engage
that project's environment resolution. Use `lint=False` when those side
effects are unwanted or when supplying exact text.

The current implementation uses Ruff only; it does not run a model-based
repair step. Missing tools and invocation failures can produce warnings.
Remaining diagnostics do not turn a successful batch into a failed one.

Data may include `lint` (`auto_fixed`, `remaining` diagnostic counts),
`lint_errors`, `warnings`, `import_removals` and `lint_diffs`.
A diff entry contains `file`, `rules` and a compact `diff`, or
`diff_skipped: "file_reread_recommended"` above the ratio threshold.
Formatting-only changes may not appear in `lint_diffs`, because the current
code generates them only when diagnostics were counted as auto-fixed.
Always reread files when exact output matters.
