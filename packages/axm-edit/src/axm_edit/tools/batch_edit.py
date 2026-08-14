"""BatchEditTool — atomic batch file editing for AI agents.

Registered as ``batch_edit`` via the ``axm.tools`` entry point.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from axm.tools.base import ToolResult

from axm_edit.core.engine import batch_apply
from axm_edit.core.preflight import (
    collect_preflight_diagnostics,
    partition_diagnostics,
)
from axm_edit.models.check import PreflightReport
from axm_edit.models.operations import (
    BatchResult,
    CreateOp,
    DeleteOp,
    Operation,
    ReplaceOp,
    RewriteOp,
)
from axm_edit.services.lint import filter_ruff_lines, ruff_available
from axm_edit.services.lint_diff import (
    compute_lint_diffs,
    extract_import_removals,
    extract_rules_by_file,
)

# Human-facing label for each dangerous ruff removal code surfaced in the
# leading alert block. F401 deletes an unused import; F811 drops a redefinition.
_REMOVAL_LABELS = {"F401": "unused import", "F811": "redefinition of"}


@dataclass(frozen=True)
class _LintOptions:
    """The ruff-lint knobs of a single ``batch_edit`` call.

    Grouped in one value object so the apply helper keeps a signature the
    preflight report can join without growing an argument list.
    """

    enabled: bool
    diff: bool
    diff_max_ratio: float


def _preflight(root: Path, raw_ops: list[dict[str, object]]) -> PreflightReport:
    """Run the shared read-only preflight over the batch, as authored.

    This is the exact core call ``batch_edit_check`` makes, so both surfaces
    report the same diagnostics in the same order for one batch. Strictly
    read-only: nothing is written, renamed or checkpointed here.

    Args:
        root: Project root the batch would be applied to.
        raw_ops: Operations as authored, before schema validation.

    Returns:
        The partitioned report. A batch the core cannot even parse yields an
        empty report: its canonical error is raised (and shaped) by
        :func:`_parse_operations` right after.
    """
    try:
        diagnostics = collect_preflight_diagnostics(root, raw_ops)
    except (OSError, ValueError, TypeError):
        return PreflightReport()
    return partition_diagnostics(diagnostics)


def _preflight_payload(report: PreflightReport) -> dict[str, object]:
    """Serialise *report* into the nested ``data["preflight"]`` entry.

    Nested on purpose: ``data["warnings"]`` already carries the ruff
    messages of :func:`_apply_lint`, and the two channels must not mix.
    """
    return {
        "diagnostics": [item.model_dump() for item in report.diagnostics],
        "errors": [item.model_dump() for item in report.errors],
        "warnings": [item.model_dump() for item in report.warnings],
        "blocking": report.blocking,
    }


def _blocked_result(report: PreflightReport) -> ToolResult:
    """Shape the refusal of a batch the preflight blocked, before any write.

    No checkpoint identifier is exposed because none was taken: the batch
    stops before ``create_checkpoint`` and ``batch_apply``.
    """
    data: dict[str, object] = {
        "preflight": _preflight_payload(report),
        "applied": 0,
        "details": [],
    }
    error = (
        f"Preflight blocked the batch: {len(report.errors)} error(s),"
        " nothing was written."
    )
    return ToolResult(
        success=False,
        data=data,
        error=error,
        text=render_text(BatchResult(success=False, error=error), [], data),
    )


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
    if not ruff_available(root):
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


def _make_path_resolver(root: Path) -> Callable[[str], str]:
    """Build a resolver mapping a raw ruff path to the *root*-relative key."""

    def _resolve(raw: str) -> str:
        candidate = Path(raw)
        if candidate.is_absolute():
            try:
                return str(candidate.relative_to(root))
            except ValueError:
                return raw
        return raw

    return _resolve


def _lint_diffs(
    root: Path,
    post_agent: dict[str, str],
    post_lint: dict[str, str],
    auto_fixed: list[str],
    max_ratio: float,
) -> list[dict[str, object]]:
    """Compute per-file lint diffs between agent and post-lint snapshots."""
    rules_by_file = extract_rules_by_file(
        auto_fixed, path_resolver=_make_path_resolver(root)
    )
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

    if auto_fixed:
        removals = extract_import_removals(
            auto_fixed, path_resolver=_make_path_resolver(root)
        )
        flat = [
            {"name": r.name, "file": r.file, "code": r.code}
            for file_removals in removals.values()
            for r in file_removals
        ]
        if flat:
            data["import_removals"] = flat

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
    delete and ``»`` a whole-file rewrite. Every operated-on file is listed
    verbatim, so the reader sees
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
        elif isinstance(op, RewriteOp):
            lines.append(f"» {op.file} (rewrite)")
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


def _render_import_alerts(data: dict[str, object]) -> list[str]:
    """Render one leading ⚠ alert line per dangerous F401/F811 removal.

    Reads the ``import_removals`` entries written by :func:`_apply_lint`
    (each a ``{"name", "file", "code"}`` dict) and turns them into saillant,
    self-explanatory warnings naming the symbol, file and ruff code. Returns
    an empty list when no dangerous removal was recorded, so a clean batch
    prepends nothing (no false positive).
    """
    removals = data.get("import_removals")
    if not isinstance(removals, list):
        return []
    lines: list[str] = []
    for entry in removals:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "?")
        file = str(entry.get("file") or "?")
        code = str(entry.get("code") or "?")
        label = _REMOVAL_LABELS.get(code, "symbol")
        lines.append(
            f"⚠ lint removed {label} `{name}` from {file} ({code})"
            f" — add `{name}` and its first consumer in the same batch,"
            f" or this removal will break a later edit"
        )
    return lines


def _render_error_lines(result: BatchResult) -> list[str]:
    """Render one ``{file}:{line}: {message}`` line per validation error.

    The locator *prefixes* the line (right after the indentation) so an
    editor, a quickfix parser (``vim -q``) or a terminal cmd-click resolves
    the position directly; a leading sigil would defeat all three. It is
    composed here from the structured :attr:`ValidationError.file` /
    :attr:`ValidationError.line` fields — never scraped out of ``error``.

    When the engine could not locate the failure (``line is None``) the
    locator degrades to ``{file}:``: no placeholder ``0``, no ``None``. The
    engine message is appended verbatim — it was already truncated upstream
    and must be neither re-rendered nor re-truncated. Errors are emitted in
    ``result.details`` order, one line each.
    """
    lines: list[str] = []
    for d in result.details:
        suffix = f" [expected: {d.expected}]" if d.expected else ""
        locator = f"{d.file}:{d.line}:" if d.line is not None else f"{d.file}:"
        lines.append(f"  {locator} {d.error or 'validation error'}{suffix}")
    return lines


def _diagnostic_hint(entry: dict[str, object]) -> str:
    """Return the remediation advice of a serialised diagnostic, if any.

    ``hint`` is the canonical key of
    :class:`~axm_edit.models.check.CheckDiagnostic`; ``remediation`` is
    accepted as a synonym so a payload spelled either way still renders its
    advice instead of silently dropping it.
    """
    for key in ("hint", "remediation"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _render_preflight_diagnostic(entry: dict[str, object]) -> list[str]:
    """Render one diagnostic as a located line plus its remediation line."""
    lines = [
        f"  [{entry.get('severity', 'error')}] op#{entry.get('op_index', '?')}"
        f" {entry.get('file', '?')}: {entry.get('code', '?')}"
        f" — {entry.get('message', '')}"
    ]
    hint = _diagnostic_hint(entry)
    if hint:
        lines.append(f"      hint: {hint}")
    return lines


def _render_preflight_lines(data: dict[str, object]) -> list[str]:
    """Render every preflight diagnostic carried by ``data["preflight"]``.

    Blocking errors and non-blocking warnings render identically — each
    names its file, its operation index and its remediation — so a refused
    batch and an applied-with-warnings batch read the same way.
    """
    report = data.get("preflight")
    if not isinstance(report, dict):
        return []
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, list):
        return []
    return [
        line
        for entry in diagnostics
        if isinstance(entry, dict)
        for line in _render_preflight_diagnostic(entry)
    ]


def _preflight_blocking(data: dict[str, object]) -> bool:
    """Whether ``data["preflight"]`` reports a batch-blocking verdict."""
    report = data.get("preflight")
    return isinstance(report, dict) and bool(report.get("blocking"))


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
    alerts = _render_import_alerts(data)
    preflight = _render_preflight_lines(data)
    if result.success:
        s = result.summary
        header = (
            f"batch_edit | ✓ | {s.get('modified', 0)} modified"
            f" · {s.get('created', 0)} created · {s.get('deleted', 0)} deleted"
            f" · {result.applied} edit{'s' if result.applied != 1 else ''}"
        )
        lines = [
            *alerts,
            header,
            *_render_op_lines(parsed),
            *preflight,
            *_render_lint_lines(data),
        ]
        return "\n".join(lines)

    label = "PREFLIGHT" if _preflight_blocking(data) else "ROLLBACK"
    header = f"batch_edit | ✗ {label} | {result.error or 'failed'}"
    lines = [
        *alerts,
        header,
        *_render_op_lines(parsed),
        *preflight,
        *_render_error_lines(result),
    ]
    return "\n".join(lines)


def _run_batch(
    root: Path,
    parsed: list[Operation],
    report: PreflightReport,
    options: _LintOptions,
) -> ToolResult:
    """Apply *parsed* ops under *root*, optionally lint, and build the result.

    *report* is the non-blocking preflight verdict already computed on the
    same batch: it is carried into ``data["preflight"]`` without touching
    any pre-existing payload key.
    """
    result = batch_apply(root, parsed)

    data: dict[str, object] = {
        "checkpoint": result.checkpoint,
        "applied": result.applied,
        "summary": result.summary,
        "details": [d.model_dump(exclude_none=True) for d in result.details]
        if result.details
        else [],
        "preflight": _preflight_payload(report),
    }

    if result.success and options.enabled:
        py_files = _collect_python_files(root, parsed)
        if py_files:
            _apply_lint(
                root,
                py_files,
                data,
                lint_diff=options.diff,
                lint_diff_max_ratio=options.diff_max_ratio,
            )

    return ToolResult(
        success=result.success,
        data=data,
        error=result.error,
        text=render_text(result, parsed, data),
    )


def _prepare_operations(raw_ops: list[dict[str, object]]) -> list[Operation]:
    """Parse *raw_ops*, re-raising a schema failure as a caller-facing error.

    Keeps the ``Invalid operations: …`` wording of the parse failure while
    letting :meth:`BatchEditTool.execute` funnel every failure mode through
    a single ``except`` clause.

    Args:
        raw_ops: Operations as authored, in batch order.

    Returns:
        The parsed operations, in the same order.

    Raises:
        ValueError: When an entry does not match the operation schema.
    """
    try:
        return _parse_operations(raw_ops)
    except (ValueError, TypeError) as exc:
        msg = f"Invalid operations: {exc}"
        raise ValueError(msg) from exc


_REWRITE_WIRE_KEY = "checksum"
_REWRITE_FIELD_KEY = "expected_checksum"


def _normalised_rewrite(raw: dict[str, object]) -> dict[str, object]:
    """Carry a rewrite digest under the payload key the preflight declares.

    :class:`~axm_edit.models.operations.RewriteOp` names the digest field
    ``expected_checksum`` while the preflight declares the payload key
    ``checksum``, so an agent may legitimately author either spelling.
    Normalising once, before the preflight runs, keeps both layers seeing the
    shape they declare. Every non-rewrite operation is returned untouched.

    Args:
        raw: One operation mapping, as authored.

    Returns:
        The same mapping when there is nothing to normalise, else a copy
        carrying the digest under ``checksum``.
    """
    if raw.get("op") != "rewrite":
        return raw
    if _REWRITE_WIRE_KEY in raw or _REWRITE_FIELD_KEY not in raw:
        return raw
    normalised = {k: v for k, v in raw.items() if k != _REWRITE_FIELD_KEY}
    normalised[_REWRITE_WIRE_KEY] = raw[_REWRITE_FIELD_KEY]
    return normalised


def _rewrite_from_raw(raw: dict[str, object]) -> RewriteOp:
    """Validate a raw ``rewrite`` mapping into its :class:`RewriteOp` model.

    Accepts the digest under either the wire key ``checksum`` or the model
    field name ``expected_checksum``.

    Args:
        raw: The rewrite mapping, as authored.

    Returns:
        The validated operation.
    """
    payload = {k: v for k, v in raw.items() if k != _REWRITE_WIRE_KEY}
    if _REWRITE_WIRE_KEY in raw:
        payload[_REWRITE_FIELD_KEY] = raw[_REWRITE_WIRE_KEY]
    return RewriteOp.model_validate(payload)


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
        elif op_type == "rewrite":
            parsed.append(_rewrite_from_raw(raw))
        else:
            msg = f"Unknown operation type: {op_type}"
            raise ValueError(msg)
    return parsed


class BatchEditTool:
    """Atomic batch file editing for AI agents.

    Replaces, rewrites, creates, and deletes files in a single atomic
    operation.
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
            operations: List of operation dicts with ``op`` discriminator —
                ``replace``, ``create``, ``delete`` or ``rewrite`` (a
                whole-file replacement carrying the exact bytes, guarded by
                the ``expected_checksum`` of the current ones).
            lint: Run ruff --fix on changed Python files after apply.
            lint_diff: Surface per-file diffs of post-lint mutations.
            lint_diff_max_ratio: Fallback threshold (diff / file size).

        Returns:
            ToolResult with applied counts, the ``checkpoint`` snapshot
            payload (a JSON string, not a SHA) to pass back to
            ``batch_rollback``, and the ``preflight`` report (diagnostics,
            warnings and blocking verdict). A blocking preflight refuses the
            batch before any checkpoint or write, so the payload then
            carries no checkpoint at all.
        """
        raw_operations: list[dict[str, object]] = [
            _normalised_rewrite(raw) for raw in operations or []
        ]

        if not raw_operations:
            return ToolResult(
                success=False,
                error="No operations provided",
            )

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )
            report = _preflight(root, raw_operations)
            if report.blocking:
                return _blocked_result(report)
            return _run_batch(
                root,
                _prepare_operations(raw_operations),
                report,
                _LintOptions(
                    enabled=lint,
                    diff=lint_diff,
                    diff_max_ratio=lint_diff_max_ratio,
                ),
            )
        except (OSError, ValueError, TypeError) as exc:
            return ToolResult(success=False, error=str(exc))
