"""Integration tests: LintingRule.check over a real fixture tree, exercising
the run_in_project subprocess returncode semantics.

Relocated from tests/unit/core/rules/test_quality_rules.py — these consume a
tmp_path-backed project fixture (real I/O) so they belong to the integration
tier even though run_in_project is monkeypatched in-body.

AXM-1958: LintingRule must fail loud on subprocess env-failure / timeout,
never report a green 100 off empty stdout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core.rules.quality_rules import LintingRule
from axm_audit.models import Severity

_PATCH = "axm_audit.core.rules.quality_rules.run_in_project"


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    """A minimal project tree with src/ so LintingRule.check_src passes."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    return tmp_path


@pytest.mark.integration
def test_lint_timeout_fails_loud_not_green(
    project_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1: a lint subprocess timeout (rc=124, empty stdout) fails loud."""

    def _timed_out(*_a: object, **_kw: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ruff"], returncode=124, stdout="", stderr="timed out"
        )

    monkeypatch.setattr(_PATCH, _timed_out)

    result = LintingRule().check(project_path)

    assert result.passed is False
    assert result.severity is Severity.ERROR
    assert result.score != 100
