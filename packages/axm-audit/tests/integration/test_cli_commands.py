"""Integration tests for the CLI commands (audit/fix/test/test-quality/version).

Each test invokes a cyclopts command function directly with a real
``tmp_path``-rooted toy project so we exercise the full chain
(CLI -> formatter -> auditor / pipeline) without a subprocess.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from axm_audit.cli import (
    audit,
    fix,
    version,
)
from axm_audit.cli import (
    test as cli_test,
)
from axm_audit.cli import (
    test_quality as cli_test_quality,
)

# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


def test_version_prints_axm_audit_prefix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`version` prints ``axm-audit <ver>`` to stdout."""
    version()
    out = capsys.readouterr().out
    assert out.startswith("axm-audit ")


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def test_audit_invalid_path_exits_with_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`audit` on a non-directory path exits 1 and writes to stderr."""
    with pytest.raises(SystemExit) as excinfo:
        audit(path="/nonexistent/path/xyz-axm-cli")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_audit_agent_output_runs_through_formatter(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit --agent` exercises the agent formatter on a stubbed result."""
    pkg = tmp_path / "proj"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    fake_result = MagicMock(
        checks=[
            MagicMock(
                passed=True,
                rule_id="QUALITY_LINT",
                message="ok",
                text=None,
                details=None,
                fix_hint=None,
            )
        ],
        quality_score=100,
        grade="A",
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    audit(path=str(pkg), agent=True)
    out = capsys.readouterr().out
    assert "audit" in out.lower()


def test_audit_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit --json` emits valid JSON to stdout."""
    pkg = tmp_path / "proj_json"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project",
        lambda *a, **kw: MagicMock(quality_score=100),
    )
    monkeypatch.setattr(
        "axm_audit.cli.format_json",
        lambda result: {"score": 100, "checks": []},
    )
    audit(path=str(pkg), json_output=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["score"] == 100


def test_audit_exits_when_score_below_threshold(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit` exits 1 when ``quality_score`` is below PASS_THRESHOLD."""
    pkg = tmp_path / "proj_fail"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')

    fake_result = MagicMock(
        checks=[
            MagicMock(
                passed=False,
                rule_id="QUALITY_LINT",
                message="bad",
                text="some text",
                details=None,
                fix_hint="run ruff",
                category="lint",
                score=10,
                metadata=None,
            )
        ],
        quality_score=10,
        grade="F",
        project_path=str(pkg),
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    with pytest.raises(SystemExit) as excinfo:
        audit(path=str(pkg))
    assert excinfo.value.code == 1
    capsys.readouterr()  # drain


# ---------------------------------------------------------------------------
# test (CLI)
# ---------------------------------------------------------------------------


def test_test_cli_invalid_path_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`test` exits 1 with stderr on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        cli_test(path="/nonexistent/xyz-test")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_test_cli_agent_renders_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test --agent` formats via format_audit_test_text."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test"
    project.mkdir()
    report = TestReport(passed=3, failed=0, errors=0, skipped=0, duration=0.1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    cli_test(path=str(project), agent=True)
    out = capsys.readouterr().out
    assert "audit_test |" in out
    assert "3 passed" in out


def test_test_cli_default_emits_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``--agent``, `test` emits a JSON dataclass dump."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test_json"
    project.mkdir()
    report = TestReport(passed=1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    cli_test(path=str(project), agent=False)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["passed"] == 1


def test_test_cli_failure_exits_with_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test` exits 1 when the report has any failures/errors."""
    from axm_audit.core.test_runner import TestReport

    project = tmp_path / "proj_test_fail"
    project.mkdir()
    report = TestReport(passed=0, failed=1)
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", lambda *a, **kw: report)
    with pytest.raises(SystemExit) as excinfo:
        cli_test(path=str(project), agent=False)
    assert excinfo.value.code == 1
    capsys.readouterr()


# ---------------------------------------------------------------------------
# test-quality
# ---------------------------------------------------------------------------


def test_test_quality_invalid_path_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`test-quality` exits 1 on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        cli_test_quality(path="/nonexistent/xyz-tq")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


def test_test_quality_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test-quality --json` emits structured JSON output."""
    fake_result = MagicMock(
        checks=[],
        quality_score=100,
        grade="A",
        project_path=str(tmp_path),
    )
    monkeypatch.setattr(
        "axm_audit.core.auditor.audit_project", lambda *a, **kw: fake_result
    )
    project = tmp_path / "proj_tq_json"
    project.mkdir()
    cli_test_quality(path=str(project), json_output=True)
    out = capsys.readouterr().out
    json.loads(out)


# ---------------------------------------------------------------------------
# fix (CLI)
# ---------------------------------------------------------------------------


def test_fix_invalid_path_exits(capsys: pytest.CaptureFixture[str]) -> None:
    """`fix` exits 1 with stderr on a non-directory path."""
    with pytest.raises(SystemExit) as excinfo:
        fix(path="/nonexistent/xyz-fix")
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Not a directory" in err


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
