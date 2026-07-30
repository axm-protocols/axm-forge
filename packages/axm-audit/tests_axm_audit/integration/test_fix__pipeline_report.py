"""Integration tests for the ``fix`` CLI command dry-run report path."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_audit.cli import fix


def test_fix_dryrun_runs_against_minimal_pkg(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`fix` (default dry-run) prints a pipeline report header."""
    from axm_audit.core.fix.models import PipelineReport
    from axm_audit.core.test_runner import TestReport

    pkg = tmp_path / "minimal_fix"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "x"
            version = "0"
            """
        )
    )
    (pkg / "src" / "x").mkdir(parents=True)
    (pkg / "src" / "x" / "__init__.py").write_text("")
    (pkg / "tests").mkdir()

    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *a, **kw: TestReport(passed=0, failed=0),
    )

    def _fake_run(project_path: Path, *, apply: bool, rules: Any) -> PipelineReport:
        return PipelineReport(applied=apply)

    monkeypatch.setattr("axm_audit.core.fix.run", _fake_run)
    fix(path=str(pkg))
    out = capsys.readouterr().out
    # The report header is always present; we just want stdout to be populated.
    assert out.strip() != ""
