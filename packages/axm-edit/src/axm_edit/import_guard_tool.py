"""BatchEditImportGuardTool — warn-only orphan-import guard for op sets.

This is a *thin interface layer* around the pure detector
:func:`axm_edit.import_guard.detect_orphan_imports`. It unpacks a
``batch_edit`` operation set (``{path, operations}``), delegates the analysis to
the core, and shapes the verdict into a :class:`~axm.tools.base.ToolResult`. It
carries **no** business logic of its own and, like the detector, performs no
mutation and no I/O on the target project — it only reports.

Registered as ``batch_edit_import_guard`` via the ``axm.tools`` entry point,
which yields MCP + CLI (``axm batch_edit_import_guard``) + DAG ``tool_node`` for
free.

**Warn-only rollout.** This tool is available and reporting, but nothing gates
on it: ``batch_edit``'s mutation semantics are unchanged and there is no
fail-closed / preflight wiring here. Turning the guard into a blocking gate is a
distinct, later, separately-reversible decision — do not infer it from this
tool's existence.
"""

from __future__ import annotations

from axm.tools.base import ToolResult

from axm_edit.import_guard import detect_orphan_imports

__all__ = ["BatchEditImportGuardTool"]


def _render_text(*, verdict: bool, violations: list[dict[str, object]]) -> str:
    """Render a compact LLM-facing view of the guard verdict.

    The header carries the global status — ``✓`` when the batch is clean, or
    ``✗`` with the orphan count otherwise — followed by one ``! file: name``
    line per violation so no structured field is lost in the text view.
    """
    if verdict:
        return "batch_edit_import_guard | ✓ | no orphan imports"
    n = len(violations)
    header = f"batch_edit_import_guard | ✗ | {n} orphan import{'s' if n != 1 else ''}"
    lines = [header]
    for v in violations:
        lines.append(f"  ! {v.get('file', '?')}: {v.get('imported_name', '?')}")
    return "\n".join(lines)


class BatchEditImportGuardTool:
    """Warn-only orphan-import guard over a ``batch_edit`` operation set.

    Delegates to :func:`detect_orphan_imports` and returns the structured
    verdict without ever touching the filesystem. Registered as
    ``batch_edit_import_guard`` via the ``axm.tools`` entry point.

    Warn-only: this tool reports; it does not gate ``batch_edit`` and does not
    mutate anything.
    """

    expose_directly = True
    domain = "edit"
    tags = frozenset({"edit", "guard", "imports", "warn-only"})

    agent_hint: str = (
        "Warn-only: flag imports a batch_edit op set adds without an in-batch"
        " consumer (orphan imports). Read-only — never mutates files and never"
        " gates batch_edit."
    )

    @property
    def name(self) -> str:
        """Tool name used for MCP registration."""
        return "batch_edit_import_guard"

    def execute(
        self,
        *,
        path: str = ".",
        operations: list[dict[str, object]] | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Report orphan imports in a ``batch_edit`` operation set (warn-only).

        Args:
            path: Project root the op set targets (carried into the op set;
                never read from or written to — the guard is pure).
            operations: The ``batch_edit`` operation list
                (``[{op, file, edits|content}]``).

        Returns:
            ``ToolResult(success=True, data={"verdict", "violations"})`` where
            ``verdict`` is ``True`` iff no orphan import was found and
            ``violations`` is the list of ``{file, imported_name, reason}``
            dicts; ``ToolResult(success=False, error=...)`` on internal error.
        """
        try:
            operation_set: dict[str, object] = {
                "path": path,
                "operations": operations or [],
            }
            report = detect_orphan_imports(operation_set)
            violations = [v.model_dump() for v in report.violations]
            verdict = report.verdict
            return ToolResult(
                success=True,
                data={"verdict": verdict, "violations": violations},
                text=_render_text(verdict=verdict, violations=violations),
            )
        except Exception as exc:  # noqa: BLE001 — MCP boundary: never raise
            return ToolResult(success=False, error=str(exc))
