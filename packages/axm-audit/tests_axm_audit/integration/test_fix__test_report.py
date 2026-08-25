"""Integration tests for the ``fix`` CLI command red-baseline warning path."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.cli import fix


def test_fix_warns_on_red_baseline(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`fix` warns on stderr when the pre-pipeline test baseline is red."""
    from axm_audit.core.fix.models import PipelineReport
    from axm_audit.core.test_runner import TestReport

    pkg = tmp_path / "red_baseline"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname="x"\nversion="0"\n')
    (pkg / "src" / "x").mkdir(parents=True)
    (pkg / "src" / "x" / "__init__.py").write_text("")
    (pkg / "tests").mkdir()

    monkeypatch.setattr(
        "axm_audit.core.test_runner.run_tests",
        lambda *a, **kw: TestReport(passed=1, failed=2, errors=1),
    )
    monkeypatch.setattr(
        "axm_audit.core.fix.run",
        lambda project_path, *, apply, rules: PipelineReport(applied=apply),
    )
    fix(path=str(pkg))
    err = capsys.readouterr().err
    assert "baseline test suite is red" in err
