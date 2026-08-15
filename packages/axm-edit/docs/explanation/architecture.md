# Architecture

Design decisions and module layout for `axm-edit`.

## Design: 1 Tool, 1 JSON

The core design choice is a **single `batch_edit` tool** that handles replace, rewrite, create, and delete operations in one atomic call. A refactor that modifies, creates, and deletes files in the same operation requires just 1 tool call instead of N.

## Module layout

```
src/axm_edit/
├── __init__.py              # Package root
├── models/
│   └── operations.py        # Pydantic models (Edit, ReplaceOp, CreateOp, DeleteOp, RewriteOp, BatchResult)
├── core/
│   ├── engine.py            # Validate-then-apply batch engine
│   ├── diagnostics.py       # Near-miss renderer (markers, Unicode naming, bounds)
│   ├── precheck.py          # Pure in-memory rules (edit keys, anchor shape, rewrite payload keys)
│   ├── precheck_fs.py       # Filesystem-resolving rules (anchors on disk, create targets, rewrite targets, line length)
│   ├── preflight.py         # Shared read-only preflight: merges + partitions the rules
│   ├── rewrite.py           # Pure rewrite-target predicate shared by the dry run and the apply path
│   ├── atomic_write.py      # Atomic + durable whole-file replacement (temp sibling, os.replace, fsync)
│   └── checkpoint.py        # Targeted per-path snapshot / rollback (no git)
├── services/
│   ├── lint.py              # filter_ruff_lines — post-apply ruff diagnostic filtering
│   └── lint_diff.py         # compute_lint_diffs / extract_rules_by_file — tagged lint diffs
├── tools/
│   ├── batch_edit.py         # BatchEditTool (AXMTool protocol)
│   ├── batch_edit_check.py   # BatchEditCheckTool — dry-run surface over core/preflight.py
│   ├── batch_rollback.py     # BatchRollbackTool (AXMTool protocol)
│   ├── read_file.py          # ReadFileTool (AXMTool protocol)
│   ├── write_file.py         # WriteFileTool (AXMTool protocol)
│   ├── edit_file.py          # EditFileTool (AXMTool protocol)
│   ├── search_files.py       # SearchFilesTool (AXMTool protocol)
│   ├── list_dir.py           # ListDirTool (AXMTool protocol)
│   └── run_command.py        # RunCommandTool (AXMTool protocol)
└── utils/
    └── __init__.py           # Shared utilities (is_binary, resolve_safe)
```

## Filesystem-tool confinement

Every filesystem tool takes a **project `root` (the `path` argument) plus a
`file`/`cwd` relative to it**, and resolves that target through the single
canonical `resolve_safe(root, relative)` resolver in `utils`. Containment is
OS-faithful: the path is fully resolved (following `..` segments, symlinks and
absolute targets to their real location) and rejected if the result does not
stay under `root` — no ad-hoc string `..` pre-filter that could diverge from the
engine/checkpoint view.

The stance is **deliberately uniform across all fs tools** — there is no
read-vs-write asymmetry:

| Tool | Confined via `resolve_safe` |
|---|---|
| `read_file` | ✅ |
| `search_files` | ✅ |
| `list_dir` | ✅ |
| `run_command` (cwd) | ✅ |
| `write_file` | ✅ |
| `edit_file` | ✅ |

`write_file` and `edit_file` historically took a single absolute `path` and were
therefore *unconfined*, which was the one remaining asymmetry: a read was
sandboxed but a write could land anywhere. They now follow the same
`path` (root) + `file` (relative) contract as the read-side tools, route the
target through `resolve_safe` before any `mkdir`/`write_text`/open, and refuse
an escaping target (absolute path outside root, or `..` traversal) with
`ToolResult(success=False)` (MCP) / a non-zero exit with the error on stderr
(CLI). Parent-directory creation for a write happens **only inside `root`**.

## The line-shift problem

When an edit at line 10 replaces 2 lines with 3 lines, every line number after 10 shifts by +1. If a second edit targets line 15 of the **original** file, applying it after the first edit would hit the wrong line.

**Solution:** All line numbers in edits reference the **original file** (the snapshot the agent read). The engine:

1. Reads the file once (snapshot)
2. Validates **all** `old` anchors against the snapshot
3. Sorts edits **bottom-to-top** (descending line number)
4. Applies in that order — upper lines are never shifted by lower edits
5. Writes the result

## Near-miss diagnostics

When a replace anchor resolves to **zero** matches, the engine no longer returns a flat "content not found" verdict: `_not_found_error` — the single construction site for that error — delegates the explanation to `core/diagnostics.py::explain_near_miss(lines, old)` and only transposes its verdict into the `ValidationError` structure.

The split of responsibility is strict, so there is one renderer and one construction site:

| Layer | Owns |
|---|---|
| `core/diagnostics.py` | finding the closest window (`closest_candidate`, similarity ≥ `SIMILARITY_THRESHOLD`), detecting the line-boundary case, and **all** rendering — `<TAB>`, one `<SP>` per trailing space, `<NBSP>`, `<CR>`/`<LF>`, Unicode names (`<EM DASH>`, `<RIGHT SINGLE QUOTATION MARK>`, …) — the whole message bounded by `MAX_DIAGNOSTIC_CHARS` |
| `core/engine.py` | calling that renderer **only on the zero-match path** (after `_all_match_lines` came back empty, so the matching hot loop keeps its cost) and filling the structured `ValidationError.line` / `.actual` from the returned `Candidate` |

What a caller gets back:

- **near miss found** — `error` names the candidate's 1-based line and the marker for the differing character (the raw character is never echoed), `line` = `Candidate.line`, `actual` = `Candidate.text` (the raw window text, unrendered, so a caller can still diff it itself)
- **anchor swallowed a line break** — the message names the first of the two joined lines and carries the `<LF>` marker
- **nothing similar enough** — the message says no similar line was found, and `line` / `actual` stay `None`, which is what distinguishes a genuinely absent anchor from a locatable near miss

Two invariants keep the report usable: the engine strips line terminators before handing the snapshot to the renderer (so `Candidate.text` honours its "terminators excluded" contract), and it never re-appends the raw candidate line — a 10 000-character line is summarised by the renderer, never dumped into the error.

The **ambiguous** branch (an anchor matching ≥ 2 lines) is bounded by the same rule. `_all_match_lines` still returns *every* hit — the count announced in the message stays exact — but the list itself is rendered by `core/diagnostics.py::format_match_lines`, which keeps at most `MAX_LISTED_MATCH_LINES` (5) line numbers and summarises the rest with a ` (+N more)` suffix. An anchor repeated 12 times therefore reports `Ambiguous match: 'old' snippet found on 12 lines (2, 4, 6, 8, 10 (+7 more)); disambiguate with a 'line' hint` instead of an unreadable, token-heavy dump. The bounding happens **once**, at that single construction site: `tools/batch_edit.py::_render_error_lines` forwards `ValidationError.error` verbatim and adds no truncation of its own.

The **hinted** branch (an edit carrying a `line` hint whose anchor is not found there) is enriched at that same construction site, and strictly by **append**: the historical wording `Content not found at or near hint line` is preserved verbatim — a caller matching on it keeps working — and the explanation follows it after a colon. `_hint_miss_message` branches on what `_actual_at` returned for the hint. When the hint sits inside the file, the character-level comparison is delegated to `core/diagnostics.py::explain_difference(old, actual)`, which names the 1-based column of the first difference and renders both sides through `render_invisibles`, so an invisible `<NBSP>`, a `<TAB>` or a smart quote becomes visible instead of two lines looking identical. When the hint points past the end of the file, the message states the file's real length instead (`… the hint points past the end of the file, which has 3 lines`), so the caller sees the hint is out of range rather than suspecting the anchor. The structured `line` / `actual` fields keep their existing contract, and no comparison logic is duplicated in the engine — `core/diagnostics.py` remains the single owner of the rendering.

## Atomicity

- **Checkpoint**: before applying, every path the batch will touch is snapshotted in-process — its prior existence plus original bytes — keyed by resolved relative path (no git involvement)
- **Validation first**: All checks pass before any file is touched
- **Anchor re-verification (TOCTOU guard)**: validation resolves each replace edit's `old` anchor to a line range, but the file could change on disk before the apply phase splices it. Immediately before each splice, the apply step re-confirms that the resolved range still matches `old` (using the same exact/dedented matchers as resolution). If the file drifted, the edit is **not** spliced at the now-stale location — the whole batch aborts, rolls back via the checkpoint, and returns `BatchResult(success=False)` with a drift error
- **Best-effort apply with automatic rollback**: atomicity is *announced at validation*, not at the OS level. Once validation passes the apply phase is best-effort: **any** exception raised mid-apply — anchor drift, a `write_text`/`unlink`/`mkdir` failure, a permission error — triggers a rollback to the pre-apply checkpoint and returns `BatchResult(success=False)` with the error. If the rollback itself cannot fully restore every snapshotted path (a filesystem error while undoing), that is surfaced via `BatchResult.rollback_failed=True`
- **Rollback is a strict inverse**: `rollback` (and the `batch_rollback` tool) restores **only** the snapshotted paths (rewrite original bytes, remove files that were absent before, recreate deleted files) and touches nothing else — no `git checkout`/`clean`/`stash`. It is best-effort: every captured path is attempted even if an earlier one fails, and the outcome is returned as a `RollbackResult` (`restored` / `unrestored` path lists, plus `ok`) so a partial rollback is detectable. Directory pruning is also strict: only the directories the **batch itself created** (recorded in the snapshot) are removed when empty — a pre-existing empty directory that merely contained a batch-created file is never deleted
- **Whole-file `rewrite`**: a `rewrite` goes through those very same two phases. Its target is classified during **validation** — so a missing, non-regular, binary or checksum-stale target refuses the whole batch before a single byte is written — and only then applied with `core/atomic_write.py::atomic_replace` (temp sibling + `os.replace` + fsync), so a concurrent reader never observes a half-written file. It is snapshotted by `create_checkpoint` exactly like a replaced file, so `rollback` restores its original bytes with **no dedicated code path**; a successful batch reports it as `summary["rewritten"]`, a key emitted only when the batch actually holds rewrites so replace/create/delete-only results stay byte-identical

## Preflight: the gate before the gate

`batch_apply` is the *last* line of defence, not the first. `BatchEditTool.execute` now runs `core/preflight.py::collect_preflight_diagnostics` + `partition_diagnostics` on the batch **as authored**, before parsing, before `create_checkpoint` and before `batch_apply` — the exact same core call `batch_edit_check` makes, so the dry-run tool and the mutating tool always report the same diagnostics in the same order.

- **Blocking (`severity="error"`)** — an unknown edit key, an anchor absent from the file on disk, a `create` on an existing path: `execute` returns `ToolResult(success=False)` immediately. Nothing is written, renamed or snapshotted, so the payload carries **no checkpoint at all** and the rendered header reads `batch_edit | ✗ PREFLIGHT | …` instead of `✗ ROLLBACK` (nothing was applied, so nothing was rolled back).
- **Non-blocking (`severity="warning"`)** — an ambiguous anchor, a line over ruff's 88-char default but within the project's configured `line-length`: the batch proceeds normally and the warnings ride along in the result.
- **Payload** — every run exposes `data["preflight"]` = `{diagnostics, errors, warnings, blocking}`, each entry a serialised `CheckDiagnostic` (`op_index`, `file`, `severity`, `code`, `message`, `hint`, `edit_index`, `anchor_excerpt`). It is deliberately **nested**: `data["warnings"]` already carries the post-apply ruff messages, and the two channels must not be confused.
- **Self-locating anchor diagnostics** — `op_index` alone does not say *which* edit of a multi-edit `replace` is at fault, so the anchor rules (`ANCHOR_TRIPLE_QUOTE`, `ANCHOR_NOT_WHOLE_LINE`, `ANCHOR_NOT_FOUND`, `ANCHOR_AMBIGUOUS`) also fill `edit_index` — the 0-indexed slot of the offending edit *inside* its operation — and `anchor_excerpt`, the offending anchor echoed back on a single line. The excerpt goes through the one renderer of `core/diagnostics.py`: invisibles are named (`<LF>`, `<TAB>`, `<NBSP>`, …) so it never carries a raw newline, and it is clamped to `core/precheck.py::MAX_ANCHOR_EXCERPT_CHARS` (80) with the same `...` marker as every other bounded message — no second truncation rule. Both fields stay `null` on a finding that is not edit-scoped (unknown edit key, `create` on an existing path, rewrite rules), and being optional they change no existing consumer of the report.
- **Rendering** — blocking errors and warnings render the same way, `[severity] op#N file: CODE — message` plus a `hint:` line, so a refused batch and an applied-with-warnings batch read identically. That located line is where the two self-locating fields surface: an edit-scoped diagnostic appends a trailing ` (edit #N)` fragment, and an anchor-carrying one echoes its excerpt on a dedicated `anchor: {excerpt}` line inserted just above the `hint:` line. The fragment is appended at the **end** of the located line, never spliced between `op#N` and the file, so the `file: CODE` locator prefix an editor/quickfix parser keys on stays byte-identical. Both additions are strictly conditional — a diagnostic whose `edit_index` / `anchor_excerpt` are `null` (unknown edit key, `create` on an existing path, rewrite rules) renders exactly as before — and `_blocked_result` builds its refusal text through that same renderer, so the blocking path, where the retry cost is actually paid, finally names *which* edit failed and on *what* anchor, in the payload **and** in the text a human or the CLI reads.

### Rewrite operations

The preflight core also classifies the checksum-guarded `rewrite` operation
(`{op, file, content, checksum}`), and `batch_edit_check` parses it through the
very same parser the core uses — so an agent is told a rewrite will be refused
**before** it attempts it, in the exact words the apply path would use:

One spelling detail is absorbed at the tool boundary: `RewriteOp` names the
digest field `expected_checksum` while the preflight core declares the payload
key `checksum`. `BatchEditTool.execute` therefore normalises the batch once —
`tools/batch_edit.py::_normalised_rewrite` — **before** the preflight runs, so a
rewrite authored with either spelling reaches both the diagnostics and the
parsed model, and no rule, severity or verdict is duplicated to accommodate it.
`batch_edit_check` keeps declaring `checksum` only.

- **Payload shape** — `core/precheck.py::check_rewrite_keys` reads the mapping
  *as authored* (no path resolved, no file read) and blocks on
  `rewrite_unknown_key` for any key outside `file`, `content` and `checksum`
  (`overwrite` in particular is **not** an escape hatch), and on
  `rewrite_checksum_required` when no digest is declared.
- **On-disk target** — `core/precheck_fs.py::check_rewrite_targets` observes the
  facts once (does it exist, is it a regular file, the sha256 of the bytes on
  disk) and hands them to the shared predicate
  `core/rewrite.py::classify_rewrite_target`. Its returned code **is** the
  diagnostic code — `rewrite_target_missing`, `rewrite_target_not_regular`,
  `rewrite_checksum_stale` — so the dry run and the apply path can never drift
  on what a valid rewrite target is. The final path component is deliberately
  **not** followed, so a symlinked target is reported as non-regular instead of
  being mistaken for the regular file it points at.

All four codes are blocking. They carry the same `CheckDiagnostic` shape as every
other rule, so they ride the existing `merge_diagnostics` ordering and the
existing `partition_diagnostics` verdict — no ordering, severity or verdict logic
is duplicated for them.

The **mutating** path enforces the identical verdict: `core/engine.py::_validate_rewrite`
observes the same triple (does it exist, is it a regular file, the sha256 of the
bytes on disk) and hands it to that same `classify_rewrite_target`, then maps the
returned code to a `ValidationError` through the single pure helper
`_rewrite_error(code, file)` — so a refused rewrite carries the code verbatim in
its message and the engine never re-implements the decision. Two guards are
engine-specific: a path escaping the root (`resolve_safe` returning `None`) is
observed as absent, and a binary target is refused with `rewrite_target_binary`.
Validation covers the **whole** batch first, so a rewrite paired with a replace
whose anchor no longer matches leaves every target byte-identical.

Wiring the preflight in does **not** relax the engine: `batch_apply`'s own validation, its anchor re-verification and its rollback stay exactly as they are — they still guard the window between the preflight verdict and the splice.

## Encoding & line endings

- **EOL preservation**: a replace reads the file with universal-newline translation for anchor matching, but the original end-of-line style (`\r\n` vs `\n`) is detected up front and **restored on write**. Editing one line of a CRLF file leaves every untouched line as `\r\n` — only the spliced region changes — and an LF file stays LF. `CreateOp` content is written verbatim, so its embedded newlines are preserved as-authored.
- **Binary / non-UTF-8 rejection as a verdict**: before any decode, the validation gate runs `is_binary()` and decodes as UTF-8 inside a guarded read. A binary file (null bytes / mostly non-printable) or a file that is not valid UTF-8 is rejected as a `ValidationError`, yielding `BatchResult(success=False)` with a clear message — a `UnicodeDecodeError` never escapes `batch_apply`, so callers (e.g. `axm-anvil`) can rely on the all-or-nothing contract.

## Security

| Constraint | Reason |
|---|---|
| Relative paths only | No access outside the project |
| `../` blocked | No path traversal |
| `old` required for replace | No blind modifications |
| Validation before write | Fail-fast, 0 files corrupted |
| Preflight before checkpoint | A contract error (unknown edit key, absent anchor, `create` on an existing path) refuses the batch before any snapshot or write — the mutating path enforces the same rules as the dry-run tool |
| `old` re-checked at apply time | Closes the validate→apply TOCTOU window; a drifted file aborts instead of a wrong-location splice |
| Targeted path snapshot | Rollback restores only what the batch touched, never destroys unrelated work |
| `rewrite` guarded by a checksum | The preflight **and** `batch_apply` classify the target through the single shared predicate before anything is attempted: an absent target, a symlink/directory, a binary file, or a digest that no longer matches the bytes on disk refuses the batch — a concurrent modification is detected instead of being silently clobbered, and there is no `overwrite` escape hatch |
| `agent_hint` on tools | LLM-optimized description propagates to MCP — agents see what each tool does without parsing docstrings |
