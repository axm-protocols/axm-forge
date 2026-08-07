"""Strictly read-only preflight for a ``batch_edit`` operation set.

Mirrors the shape of :mod:`axm_edit.tools.batch_edit`: a module-level
:func:`render_text` plus an :class:`~axm.tools.base.AXMTool` whose
``execute`` never raises — every failure is shaped into
``ToolResult(success=False, error=...)``.

No code path here opens a file for writing, creates a directory, or calls
``batch_apply`` / ``create_checkpoint``: rule evaluation is fully delegated
to the read-only check layers of :mod:`axm_edit.core.precheck` and
:mod:`axm_edit.core.precheck_fs`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_edit.core.precheck import check_edit_keys
from axm_edit.core.precheck_fs import run_fs_checks
from axm_edit.models.check import CheckDiagnostic
from axm_edit.models.operations import CreateOp, DeleteOp, Edit, ReplaceOp

__all__ = ["BatchEditCheckTool", "render_text"]

type CheckOperation = ReplaceOp | CreateOp | DeleteOp

_EMPTY_RENDER = "batch_edit_check | ✓ | 0 diagnostic(s)"


def render_text(diagnostics: Sequence[CheckDiagnostic]) -> str:
    """Render a diagnostic set as the compact text consumed by the CLI.

    Args:
        diagnostics: Diagnostics to render, in batch order.

    Returns:
        ``"batch_edit_check | ✓ | 0 diagnostic(s)"`` when *diagnostics*
        is empty; otherwise a header plus one line per diagnostic carrying
        its ``code``, its ``message`` and its ``hint``.
    """
    if not diagnostics:
        return _EMPTY_RENDER

    lines = [f"batch_edit_check | ✗ | {len(diagnostics)} diagnostic(s)"]
    for diagnostic in diagnostics:
        lines.append(
            f"  [{diagnostic.severity}] op#{diagnostic.op_index}"
            f" {diagnostic.file}: {diagnostic.code} — {diagnostic.message}"
        )
        if diagnostic.hint:
            lines.append(f"      hint: {diagnostic.hint}")
    return "\n".join(lines)


def _sanitized_edit(raw_edit: Mapping[str, object]) -> dict[str, object]:
    """Drop the keys that are not part of the ``Edit`` schema.

    Args:
        raw_edit: Edit mapping as authored, before validation.

    Returns:
        A copy holding only the keys of
        :class:`~axm_edit.models.operations.Edit`, so a typo does not abort
        the whole pass — it is reported as ``UNKNOWN_EDIT_KEY`` instead.
    """
    allowed = tuple(Edit.model_fields)
    return {key: value for key, value in raw_edit.items() if key in allowed}


def _replace_payload(raw: Mapping[str, object]) -> dict[str, object]:
    """Return a ``replace`` payload whose edits carry only known keys.

    Args:
        raw: Operation mapping as authored.

    Returns:
        A shallow copy of *raw* with each edit sanitized.
    """
    payload = dict(raw)
    edits = payload.get("edits")
    if not isinstance(edits, list):
        return payload
    sanitized: list[object] = [
        _sanitized_edit(edit) if isinstance(edit, Mapping) else edit for edit in edits
    ]
    payload["edits"] = sanitized
    return payload


def _parse_check_operations(
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckOperation]:
    """Parse raw operation dicts into the shared operation models.

    The models are the canonical ones of
    :mod:`axm_edit.models.operations` — the checker declares no parallel
    schema of its own.

    Args:
        raw_ops: Operations as authored, in batch order.

    Returns:
        One :class:`ReplaceOp` / :class:`CreateOp` / :class:`DeleteOp` per
        entry, in the same order.

    Raises:
        ValueError: When an entry carries an unknown ``op`` discriminator
            or fails model validation.
    """
    parsed: list[CheckOperation] = []
    for raw in raw_ops:
        op_type = raw.get("op")
        if op_type == "replace":
            parsed.append(ReplaceOp.model_validate(_replace_payload(raw)))
        elif op_type == "create":
            parsed.append(CreateOp.model_validate(dict(raw)))
        elif op_type == "delete":
            parsed.append(DeleteOp.model_validate(dict(raw)))
        else:
            msg = f"Unknown operation type: {op_type}"
            raise ValueError(msg)
    return parsed


def _unknown_edit_key_diagnostics(
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckDiagnostic]:
    """Report the edit keys sanitized away before model validation.

    Args:
        raw_ops: Operations as authored, in batch order.

    Returns:
        One ``UNKNOWN_EDIT_KEY`` diagnostic per offending edit, else ``[]``.
    """
    diagnostics: list[CheckDiagnostic] = []
    for index, raw in enumerate(raw_ops):
        file = raw.get("file")
        edits = raw.get("edits")
        if raw.get("op") != "replace" or not isinstance(file, str) or not file:
            continue
        if not isinstance(edits, list):
            continue
        for edit in edits:
            if isinstance(edit, Mapping):
                diagnostics.extend(check_edit_keys(index, file, edit))
    return diagnostics


def _collect_diagnostics(
    root: Path,
    raw_ops: Sequence[Mapping[str, object]],
) -> list[CheckDiagnostic]:
    """Run every read-only check over *raw_ops* under *root*.

    Args:
        root: Project root the batch would be applied to.
        raw_ops: Operations as authored, in batch order.

    Returns:
        Every diagnostic found, sorted by increasing ``op_index``.
    """
    parsed = _parse_check_operations(raw_ops)
    diagnostics = [
        *_unknown_edit_key_diagnostics(raw_ops),
        *run_fs_checks(root, parsed),
    ]
    return sorted(diagnostics, key=lambda diagnostic: diagnostic.op_index)


class BatchEditCheckTool(AXMTool):
    """Validate a ``batch_edit`` operation set without touching the disk.

    Orchestration and shaping layer only: the rules live in
    :mod:`axm_edit.core.precheck` / :mod:`axm_edit.core.precheck_fs`.
    """

    expose_directly = False
    domain = "edit"
    tags = frozenset({"edit", "check", "preflight"})

    agent_hint: str = (
        "Preflight a batch_edit operation set read-only: reports broken"
        " anchors, creates on existing files and unknown edit keys."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_edit_check"

    def execute(
        self,
        *,
        path: str = ".",
        operations: list[dict[str, object]] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Check a batch of file operations without applying any of them.

        Args:
            path: Project root the batch would be applied to.
            operations: List of operation dicts with ``op`` discriminator.
            kwargs: Ignored extra arguments (MCP forward-compatibility).

        Returns:
            ``ToolResult(success=True)`` with ``data["ok"]`` and the
            serialised ``data["diagnostics"]`` when the check could run;
            ``ToolResult(success=False, error=...)`` when the tool itself
            failed (missing root, malformed operations). Never raises.
        """
        raw_operations: list[dict[str, object]] = operations or []

        if not raw_operations:
            return ToolResult(success=False, error="No operations provided")

        try:
            root = Path(path).resolve()
            if not root.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}",
                )
            diagnostics = _collect_diagnostics(root, raw_operations)
        except (OSError, ValueError, TypeError) as exc:
            return ToolResult(success=False, error=str(exc))

        payload: list[dict[str, object]] = [
            diagnostic.model_dump() for diagnostic in diagnostics
        ]
        data: dict[str, object] = {"ok": not diagnostics, "diagnostics": payload}
        return ToolResult(success=True, data=data, text=render_text(diagnostics))
