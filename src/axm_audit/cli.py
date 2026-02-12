"""AXM-Audit CLI entry point — Code quality auditing tool.

Usage::

    axm-audit audit .
    axm-audit audit --json
    axm-audit audit --category quality
    axm-audit version
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import cyclopts

from axm_audit.formatters import format_json, format_report

__all__ = ["app"]

app = cyclopts.App(
    name="axm-audit",
    help="AXM Audit — Python code quality auditing tool.",
)


@app.command()
def audit(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to audit"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    category: Annotated[
        str | None,
        cyclopts.Parameter(name=["--category", "-c"], help="Filter to one category"),
    ] = None,
) -> None:
    """Audit a project's code quality against the AXM standard."""
    from axm_audit.core.auditor import audit_project

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    result = audit_project(project_path, category=category)

    if json_output:
        print(json.dumps(format_json(result), indent=2))
    else:
        print(format_report(result))

    if result.quality_score is not None and result.quality_score < 100:
        raise SystemExit(1)


@app.command()
def version() -> None:
    """Show axm-audit version."""
    from axm_audit import __version__

    print(f"axm-audit {__version__}")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
