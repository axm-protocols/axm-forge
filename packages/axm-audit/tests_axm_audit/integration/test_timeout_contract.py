"""Timeout selection remains bounded and fails closed."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm_audit.core import test_runner
from axm_audit.tools.audit_test import AuditTestTool


@pytest.mark.parametrize("value", [0, -1, 86401, True, 1.5, "900"])
def test_invalid_timeout_is_rejected(tmp_path: Path, value: object) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        test_runner.run_tests(tmp_path, timeout_seconds=value)
    result = AuditTestTool().execute(path=str(tmp_path), timeout_seconds=value)
    assert not result.success
    assert "timeout_seconds" in str(result.error)


def test_nondefault_timeout_reaches_subprocess_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[int] = []

    def timeout(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs["timeout"])
        return subprocess.CompletedProcess(
            args=[], returncode=124, stdout="", stderr="timeout"
        )

    monkeypatch.setattr(test_runner, "run_in_project", timeout)
    report = test_runner.run_tests(tmp_path, timeout_seconds=1800)
    assert seen == [1800]
    assert report.timed_out and report.verdict is False and report.coverage is None

    result = AuditTestTool().execute(
        path=str(tmp_path), timeout_seconds=1800, include_cases=True
    )
    assert seen == [1800, 1800]
    assert not result.success
    assert "1800s" in str(result.error)
    assert result.data is None or "cases" not in result.data
