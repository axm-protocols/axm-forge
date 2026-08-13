"""MCP tool for the documentation gate (``mkdocs build --strict``).

Runs ``mkdocs build --strict`` in a bounded subprocess against a target package
and turns the captured log into structured :class:`DocGateFinding` records by
delegating to :func:`parse_mkdocs_output` (no parsing re-implemented here).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from axm.tools.base import AXMTool, ToolResult

from axm_audit.doc_gate.findings import DocGateFinding
from axm_audit.doc_gate.parser import parse_mkdocs_output

__all__ = ["DocGateTool"]

_DEFAULT_TIMEOUT = 120


def _summarize(findings: list[DocGateFinding]) -> str:
    """Render a compact human-readable summary of the gate findings."""
    if not findings:
        return "doc_gate: no documentation issues found"
    lines = [f"doc_gate: {len(findings)} finding(s)"]
    for finding in findings:
        page = finding.source_page or "?"
        target = finding.target or "?"
        lines.append(f"  - {finding.kind.value}: {page} -> {target}")
    return "\n".join(lines)


class DocGateTool(AXMTool):
    """Run ``mkdocs build --strict`` and report documentation-gate findings.

    Registered as ``doc_gate`` via the ``axm.tools`` entry point, so it is
    reachable as an MCP tool, as ``axm doc_gate`` on the CLI, and as a DAG node.
    """

    expose_directly = True
    domain = "audit"
    tags = frozenset({"docs", "mkdocs", "gate"})
    agent_hint = (
        "Run `mkdocs build --strict` on a package and report dead links, "
        "missing anchors and bad references as structured findings."
    )

    @property
    def name(self) -> str:
        """Return tool name for registry lookup."""
        return "doc_gate"

    def execute(
        self,
        *,
        path: str = ".",
        timeout: int = _DEFAULT_TIMEOUT,
        **kwargs: object,
    ) -> ToolResult:
        """Run the documentation gate on the target package.

        Args:
            path: Path to the package root holding ``mkdocs.yml``.
            timeout: Hard wall-clock bound (seconds) for the mkdocs subprocess.

        Returns:
            ToolResult with structured findings (``data``) plus a human summary
            (``text``) on success, or ``success=False`` with a clear error when
            mkdocs is absent, times out, or the build fails without findings.
        """
        try:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                return ToolResult(
                    success=False, error=f"Not a directory: {project_path}"
                )
            with tempfile.TemporaryDirectory() as site_dir:
                completed = subprocess.run(  # noqa: S603
                    ["mkdocs", "build", "--strict", "--site-dir", site_dir],  # noqa: S607
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="mkdocs is not installed in the environment "
                "(binary not found on PATH)",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"mkdocs build timed out after {timeout}s",
            )
        except OSError as exc:
            return ToolResult(success=False, error=str(exc))

        output = (completed.stdout or "") + (completed.stderr or "")
        findings = [] if completed.returncode == 0 else parse_mkdocs_output(output)
        if completed.returncode != 0 and not findings:
            detail = output.strip() or "no output captured"
            return ToolResult(
                success=False,
                error=f"mkdocs build failed (exit {completed.returncode}): {detail}",
            )
        data = {
            "findings": [finding.model_dump(mode="json") for finding in findings],
            "count": len(findings),
        }
        return ToolResult(success=True, data=data, text=_summarize(findings))
