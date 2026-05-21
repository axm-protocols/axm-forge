"""AXM-Audit CLI entry point — Code quality auditing tool.

Usage::

    axm-audit audit .
    axm-audit audit --json
    axm-audit audit --category lint
    axm-audit fix .
    axm-audit fix . --apply
    axm-audit test .
    axm-audit version
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import cyclopts

from axm_audit.core.rules.base import PASS_THRESHOLD
from axm_audit.formatters import (
    format_agent,
    format_agent_text,
    format_json,
    format_report,
    format_test_quality_json,
    format_test_quality_text,
)
from axm_audit.models.results import format_categories_help

__all__ = ["app"]


class _AppFacade:
    """Wraps :class:`cyclopts.App` so external iteration yields sub-apps.

    Cyclopts' own iteration yields command-name strings, which lack the
    ``.name`` attribute callers expect when introspecting registrations.
    Iterating this facade yields the underlying sub-:class:`cyclopts.App`
    objects whose ``.name`` is a tuple of registered names. All other
    attribute access and ``__call__`` delegate to the wrapped app, so
    cyclopts' own internal iteration is unaffected.
    """

    def __init__(self, app: cyclopts.App) -> None:
        self._app = app

    def __iter__(self) -> Iterator[object]:
        return iter(self._app._commands.values())

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self._app(*args, **kwargs)  # type: ignore[arg-type]

    def __getattr__(self, item: str) -> object:
        return getattr(self._app, item)


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
    agent: Annotated[
        bool,
        cyclopts.Parameter(name=["--agent"], help="Compact agent-friendly output"),
    ] = False,
    category: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--category", "-c"],
            help=(
                "Filter to one category. Accepted values:\n" + format_categories_help()
            ),
        ),
    ] = None,
) -> None:
    """Audit a project's code quality against the AXM standard."""
    from axm_audit.core.auditor import audit_project

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    result = audit_project(project_path, category=category)

    if agent:
        print(format_agent_text(format_agent(result), category=category))
    elif json_output:
        print(json.dumps(format_json(result), indent=2))
    else:
        print(format_report(result))

    if result.quality_score is not None and result.quality_score < PASS_THRESHOLD:
        raise SystemExit(1)


@app.command()
def fix(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to fix"),
    ] = ".",
    *,
    apply: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--apply"],
            help="Mutate the project (default: dry-run)",
        ),
    ] = False,
    rules: Annotated[
        str,
        cyclopts.Parameter(
            name=["--rules"],
            help="Comma-separated rule_ids to fix",
        ),
    ] = "TEST_QUALITY_PYRAMID_LEVEL,TEST_QUALITY_FILE_NAMING",
) -> None:
    """Deterministically reorganise a project's test suite."""
    from axm_audit.core.fix import format_report, run
    from axm_audit.core.test_runner import run_tests

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    baseline = run_tests(project_path)
    if baseline.failed > 0 or baseline.errors > 0:
        print(
            "⚠  baseline test suite is red "
            f"({baseline.failed} failed, {baseline.errors} error(s)) — "
            "fix the failing tests first; proceeding anyway, parity is "
            "the user's responsibility.",
            file=sys.stderr,
        )

    rule_set = {r.strip() for r in rules.split(",") if r.strip()}
    report = run(project_path, apply=apply, rules=rule_set)
    print(format_report(report, project_path))


@app.command()
def test(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to test"),
    ] = ".",
    *,
    files: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            name=["--files"],
            help="Specific test files to run",
        ),
    ] = None,
    markers: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            name=["-m", "--markers"],
            help="Pytest markers to filter",
        ),
    ] = None,
    stop_on_first: Annotated[
        bool,
        cyclopts.Parameter(
            name=["-x", "--stop-on-first"],
            help="Stop on first failure",
        ),
    ] = True,
    agent: Annotated[
        bool,
        cyclopts.Parameter(name=["--agent"], help="Compact agent-friendly output"),
    ] = False,
) -> None:
    """Run tests with structured output."""
    import dataclasses

    from axm_audit.core.test_runner import run_tests

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    report = run_tests(
        project_path,
        files=files,
        markers=markers,
        stop_on_first=stop_on_first,
    )

    if agent:
        from axm_audit.tools.audit_test_text import format_audit_test_text

        print(format_audit_test_text(report))
    else:
        print(json.dumps(dataclasses.asdict(report), indent=2))

    if report.failed > 0 or report.errors > 0:
        raise SystemExit(1)


@app.command(name="test-quality")
def test_quality(
    path: Annotated[
        str,
        cyclopts.Parameter(help="Path to project to analyse"),
    ] = ".",
    *,
    json_output: Annotated[
        bool,
        cyclopts.Parameter(name=["--json"], help="Output as JSON"),
    ] = False,
    mismatches_only: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--mismatches-only"],
            help="Show only pyramid mismatches (folder vs classified level)",
        ),
    ] = False,
    agent: Annotated[
        bool,
        cyclopts.Parameter(name=["--agent"], help="Compact agent-friendly output"),
    ] = False,
) -> None:
    """Audit test quality (pyramid, duplicates, tautologies, private imports)."""
    from axm_audit.core.auditor import audit_project

    project_path = Path(path).resolve()
    if not project_path.is_dir():
        print(f"❌ Not a directory: {project_path}", file=sys.stderr)
        raise SystemExit(1)

    result = audit_project(project_path, category="test_quality")

    if agent:
        print(format_agent_text(format_agent(result), category="test_quality"))
    elif json_output:
        print(json.dumps(format_test_quality_json(result), indent=2))
    else:
        print(format_test_quality_text(result, mismatches_only=mismatches_only))

    if result.quality_score is not None and result.quality_score < PASS_THRESHOLD:
        raise SystemExit(1)


@app.command()
def version() -> None:
    """Show axm-audit version."""
    from axm_audit import __version__

    print(f"axm-audit {__version__}")


def main() -> None:
    """Main entry point."""
    app()


# Expose facade so ``list(app)`` yields sub-Apps with ``.name`` tuples.
app = _AppFacade(app)  # type: ignore[assignment]


if __name__ == "__main__":
    main()
