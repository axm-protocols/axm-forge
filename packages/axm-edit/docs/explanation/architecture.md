# Architecture

Design decisions and module layout for `axm-edit`.

## Design: 1 Tool, 1 JSON

The core design choice is a **single `batch_edit` tool** that handles replace, create, and delete operations in one atomic call. A refactor that modifies, creates, and deletes files in the same operation requires just 1 tool call instead of N.

## Module layout

```
src/axm_edit/
├── __init__.py              # Package root
├── models/
│   └── operations.py        # Pydantic models (Edit, ReplaceOp, CreateOp, DeleteOp, BatchResult)
├── core/
│   ├── engine.py            # Validate-then-apply batch engine
│   ├── diagnostics.py       # Near-miss renderer (markers, Unicode naming, bounds)
│   └── checkpoint.py        # Targeted per-path snapshot / rollback (no git)
├── services/
│   ├── lint.py              # filter_ruff_lines — post-apply ruff diagnostic filtering
│   └── lint_diff.py         # compute_lint_diffs / extract_rules_by_file — tagged lint diffs
├── tools/
│   ├── batch_edit.py         # BatchEditTool (AXMTool protocol)
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

## Atomicity

- **Checkpoint**: before applying, every path the batch will touch is snapshotted in-process — its prior existence plus original bytes — keyed by resolved relative path (no git involvement)
- **Validation first**: All checks pass before any file is touched
- **Anchor re-verification (TOCTOU guard)**: validation resolves each replace edit's `old` anchor to a line range, but the file could change on disk before the apply phase splices it. Immediately before each splice, the apply step re-confirms that the resolved range still matches `old` (using the same exact/dedented matchers as resolution). If the file drifted, the edit is **not** spliced at the now-stale location — the whole batch aborts, rolls back via the checkpoint, and returns `BatchResult(success=False)` with a drift error
- **Best-effort apply with automatic rollback**: atomicity is *announced at validation*, not at the OS level. Once validation passes the apply phase is best-effort: **any** exception raised mid-apply — anchor drift, a `write_text`/`unlink`/`mkdir` failure, a permission error — triggers a rollback to the pre-apply checkpoint and returns `BatchResult(success=False)` with the error. If the rollback itself cannot fully restore every snapshotted path (a filesystem error while undoing), that is surfaced via `BatchResult.rollback_failed=True`
- **Rollback is a strict inverse**: `rollback` (and the `batch_rollback` tool) restores **only** the snapshotted paths (rewrite original bytes, remove files that were absent before, recreate deleted files) and touches nothing else — no `git checkout`/`clean`/`stash`. It is best-effort: every captured path is attempted even if an earlier one fails, and the outcome is returned as a `RollbackResult` (`restored` / `unrestored` path lists, plus `ok`) so a partial rollback is detectable. Directory pruning is also strict: only the directories the **batch itself created** (recorded in the snapshot) are removed when empty — a pre-existing empty directory that merely contained a batch-created file is never deleted

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
| `old` re-checked at apply time | Closes the validate→apply TOCTOU window; a drifted file aborts instead of a wrong-location splice |
| Targeted path snapshot | Rollback restores only what the batch touched, never destroys unrelated work |
| `agent_hint` on tools | LLM-optimized description propagates to MCP — agents see what each tool does without parsing docstrings |
