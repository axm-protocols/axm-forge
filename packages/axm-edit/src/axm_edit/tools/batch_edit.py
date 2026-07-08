"""BatchEditTool — atomic batch file editing for AI agents.

Registered as ``batch_edit`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.engine import batch_apply
from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Operation,
    ReplaceOp,
)
from axm_edit.services import lint as _lint
from axm_edit.services.lint import filter_ruff_lines
from axm_edit.services.lint_diff import compute_lint_diffs, extract_rules_by_file


def _collect_python_files(root: Path, operations: list[Operation]) -> list[Path]:
    """Extract resolved paths of Python files from operations."""
    paths: list[Path] = []
    for op in operations:
        if hasattr(op, "file") and op.file.endswith(".py"):
            resolved = root / op.file
            if resolved.is_file():
                paths.append(resolved)
    return sorted(set(paths))


def _ruff_check(
    root: Path,
    str_files: list[str],
    extend: list[str],
    *,
    warnings: list[str] | None = None,
) -> list[str]:
    """Run ``ruff check`` and return diagnostic lines."""
    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "ruff",
                "check",
                "--output-format=concise",
                *extend,
                *str_files,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff check failed: {exc}")
        return []

    if result.returncode > 1:
        if warnings is not None:
            warnings.append(f"ruff crashed (exit {result.returncode}), lint skipped")
        return []

    if result.returncode != 0 and result.stdout.strip():
        return filter_ruff_lines(result.stdout)
    return []


def _run_ruff(
    root: Path,
    files: list[Path],
    *,
    warnings: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Run ruff fix then check on *files*.

    Returns:
        Tuple of (auto-fixed diagnostic lines, remaining diagnostic lines).
    """
    if not _lint._has_ruff:
        if warnings is not None:
            warnings.append("ruff not found, lint skipped")
        return [], []

    str_files = [str(f) for f in files]
    extend = ["--extend-select", "I"]

    # Snapshot diagnostics before fix
    before = _ruff_check(root, str_files, extend, warnings=warnings)

    # Auto-fix what we can
    try:
        subprocess.run(
            ["uv", "run", "ruff", "check", "--fix", "--exit-zero", *extend, *str_files],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff fix failed: {exc}")
        return [], []

    # Format files
    try:
        subprocess.run(
            ["uv", "run", "ruff", "format", *str_files],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        if warnings is not None:
            warnings.append(f"ruff format failed: {exc}")

    # Check remaining after fix
    remaining = _ruff_check(root, str_files, extend, warnings=warnings)

    remaining_set = set(remaining)
    auto_fixed = [e for e in before if e not in remaining_set]

    return auto_fixed, remaining


def _snapshot_files(root: Path, py_files: list[Path]) -> dict[str, str]:
    """Read current text of *py_files*, keyed by path relative to *root*."""
    snapshot: dict[str, str] = {}
    for py_file in py_files:
        try:
            snapshot[str(py_file.relative_to(root))] = py_file.read_text()
        except OSError:
            continue
    return snapshot


def _lint_diffs(
    root: Path,
    post_agent: dict[str, str],
    post_lint: dict[str, str],
    auto_fixed: list[str],
    max_ratio: float,
) -> list[dict[str, object]]:
    """Compute per-file lint diffs between agent and post-lint snapshots."""

    def _resolve(raw: str, root: Path = root) -> str:
        candidate = Path(raw)
        if candidate.is_absolute():
            try:
                return str(candidate.relative_to(root))
            except ValueError:
                return raw
        return raw

    rules_by_file = extract_rules_by_file(auto_fixed, path_resolver=_resolve)
    return compute_lint_diffs(
        post_agent,
        post_lint,
        rules_by_file,
        max_ratio=max_ratio,
    )


def _apply_lint(
    root: Path,
    py_files: list[Path],
    data: dict[str, object],
    *,
    lint_diff: bool,
    lint_diff_max_ratio: float,
) -> None:
    """Run ruff/harness lint over *py_files* and enrich *data* in place."""
    lint_warnings: list[str] = []
    post_agent = _snapshot_files(root, py_files) if lint_diff else {}

    auto_fixed, lint_errors = _run_ruff(root, py_files, warnings=lint_warnings)

    data["lint"] = {
        "auto_fixed": len(auto_fixed),
        "remaining": len(lint_errors),
    }
    if lint_errors:
        data["lint_errors"] = lint_errors
    if lint_warnings:
        data["warnings"] = lint_warnings

    if lint_diff and auto_fixed:
        post_lint = _snapshot_files(root, py_files)
        diffs = _lint_diffs(
            root, post_agent, post_lint, auto_fixed, lint_diff_max_ratio
        )
        if diffs:
            data["lint_diffs"] = diffs


def _render_op_lines(parsed: list[Operation]) -> list[str]:
    """Render one ``{sigil} {file}`` line per operation, op order preserved.

    ``~`` marks a replace (with its edit count), ``+`` a create, ``-`` a
    delete. Every operated-on file is listed verbatim, so the reader sees
    exactly which path each op touched — information the count-only
    ``summary`` in ``data`` does not carry.
    """
    lines: list[str] = []
    for op in parsed:
        if isinstance(op, ReplaceOp):
            n = len(op.edits)
            lines.append(f"~ {op.file} ({n} edit{'s' if n != 1 else ''})")
        elif isinstance(op, CreateOp):
            lines.append(f"+ {op.file}")
        elif isinstance(op, DeleteOp):
            lines.append(f"- {op.file}")
    return lines


def _render_lint_lines(data: dict[str, object]) -> list[str]:
    """Render the lint summary, remaining errors, warnings and diffs.

    Mirrors every lint key written into ``data`` by :func:`_apply_lint`
    (``lint``, ``lint_errors``, ``warnings``, ``lint_diffs``) so the text
    view loses nothing relative to the structured payload.
    """
    lines: list[str] = []
    summary = data.get("lint")
    if isinstance(summary, dict):
        lines.append(
            f"lint: {summary.get('auto_fixed', 0)} auto-fixed"
            f" · {summary.get('remaining', 0)} remaining"
        )
    errors = data.get("lint_errors")
    if isinstance(errors, list):
        lines.extend(f"  ! {err}" for err in errors)
    warnings = data.get("warnings")
    if isinstance(warnings, list):
        lines.extend(f"  ⚠ {warn}" for warn in warnings)
    diffs = data.get("lint_diffs")
    if isinstance(diffs, list):
        for entry in diffs:
            if isinstance(entry, dict):
                lines.extend(_render_lint_diff(entry))
    return lines


def _render_lint_diff(entry: dict[str, object]) -> list[str]:
    raw_rules = entry.get("rules", [])
    rules = ", ".join(str(r) for r in raw_rules) if isinstance(raw_rules, list) else ""
    lines = [f"  {entry.get('file', '?')} [{rules}]"]
    diff = entry.get("diff")
    if isinstance(diff, str) and diff:
        lines.extend(f"    {dl}" for dl in diff.splitlines())
    elif entry.get("diff_skipped"):
        lines.append(f"    (diff skipped: {entry['diff_skipped']})")
    return lines


def render_text(
    result: BatchResult,
    parsed: list[Operation],
    data: dict[str, object],
) -> str:
    """Render a compact, ``git``-style LLM-facing view of a batch result.

    The header carries the global status — ``✓`` on success, or
    ``✗ ROLLBACK`` on failure so a partial/aborted batch is impossible to
    miss — followed by the modified/created/deleted/edits counts. Each
    operated-on file is then listed with its op sigil and edit count, every
    validation error is surfaced verbatim, and the full lint summary
    (fixes, remaining errors, warnings, diffs) is appended. Nothing in
    ``data`` is dropped; only its JSON structure is.
    """
    if result.success:
        s = result.summary
        header = (
            f"batch_edit | ✓ | {s.get('modified', 0)} modified"
            f" · {s.get('created', 0)} created · {s.get('deleted', 0)} deleted"
            f" · {result.applied} edit{'s' if result.applied != 1 else ''}"
        )
        lines = [header, *_render_op_lines(parsed), *_render_lint_lines(data)]
        return "\n".join(lines)

    header = f"batch_edit | ✗ ROLLBACK | {result.error or 'failed'}"
    lines = [header, *_render_op_lines(parsed)]
    for d in result.details:
        suffix = f" [expected: {d.expected}]" if d.expected else ""
        loc = f"{d.file}:{d.line}" if d.line is not None else d.file
        lines.append(f"  ! {loc}: {d.error or 'validation error'}{suffix}")
    return "\n".join(lines)


def _run_batch(
    root: Path,
    parsed: list[Operation],
    *,
    lint: bool,
    lint_diff: bool,
    lint_diff_max_ratio: float,
) -> ToolResult:
    """Apply *parsed* ops under *root*, optionally lint, and build the result."""
    result = batch_apply(root, parsed)

    data: dict[str, object] = {
        "checkpoint": result.checkpoint,
        "applied": result.applied,
        "summary": result.summary,
        "details": [d.model_dump(exclude_none=True) for d in result.details]
        if result.details
        else [],
    }

    if result.success and lint:
        py_files = _collect_python_files(root, parsed)
        if py_files:
            _apply_lint(
                root,
                py_files,
                data,
                lint_diff=lint_diff,
                lint_diff_max_ratio=lint_diff_max_ratio,
            )

    return ToolResult(
        success=result.success,
        data=data,
        error=result.error,
        text=render_text(result, parsed, data),
    )


def _parse_operations(raw_ops: list[dict[str, object]]) -> list[Operation]:
    """Parse raw dicts into typed Operation models.

    Uses the ``op`` discriminator to select the correct model.
    """
    parsed: list[Operation] = []
    for raw in raw_ops:
        op_type = raw.get("op")
        if op_type == "replace":
            parsed.append(ReplaceOp.model_validate(raw))
        elif op_type == "create":
            parsed.append(CreateOp.model_validate(raw))
        elif op_type == "delete":
            parsed.append(DeleteOp.model_validate(raw))
        else:
            msg = f"Unknown operation type: {op_type}"
            raise ValueError(msg)
    return parsed


class BatchEditTool:
    """Atomic batch file editing for AI agents.

    Replaces, creates, and deletes files in a single atomic operation.
    Registered as ``batch_edit`` via axm.tools entry point.
    """

    expose_directly = True
    domain = "edit"
    tags = frozenset({"edit", "atomic", "refactor"})

    agent_hint: str = (
        "Apply multiple file edits atomically via op=replace"
        " with old/new pairs. Safer than sed — validates before writing."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_edit"

    def execute(
        self,
        *,
        path: str = ".",
        operations: list[dict[str, object]] | None = None,
        lint: bool = True,
        lint_diff: bool = True,
        lint_diff_max_ratio: float = 0.5,
        **kwargs: object,
    ) -> ToolResult:
        """Execute a batch of file operations atomically.

        Args:
            path: Project root directory.
            operations: List of operation dicts with ``op`` discriminator.
            lint: Run ruff --fix on changed Python files after apply.
            lint_diff: Surface per-file diffs of post-lint mutations.
            lint_diff_max_ratio: Fallback threshold (diff / file size).

        Returns:
            ToolResult with applied counts and the ``checkpoint`` snapshot
            payload (a JSON string, not a SHA) to pass back to
            ``batch_rollback``.
        """
        raw_operations: list[dict[str, object]] = operations or []

        if not raw_operations:
            return ToolResult(
                success=False,
                error="No operations provided",
            )

        try:
            parsed = _parse_operations(raw_operations)
        except (ValueError, TypeError) as exc:
            return ToolResult(success=False, error=f"Invalid operations: {exc}")

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )

            return _run_batch(
                root,
                parsed,
                lint=lint,
                lint_diff=lint_diff,
                lint_diff_max_ratio=lint_diff_max_ratio,
            )
        except (OSError, ValueError, TypeError) as exc:
            return ToolResult(success=False, error=str(exc))
