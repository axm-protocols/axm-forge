from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from axm.tools.base import AXMTool, ToolResult
from axm_audit.core import auditor, test_runner
from axm_audit.core.pytest_env import PytestCapabilities
from axm_audit.core.rules.coverage import TestCoverageRule
from axm_audit.tools.audit import AuditTool

from axm_mcp.verify import verify_project


def test_audit_timeout_reaches_test_runner_without_leaking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-package"\nversion = "0.0.1"\n'
    )
    seen: list[int] = []

    def fake_run_pytest(*args: object, **kwargs: object) -> CompletedProcess[str]:
        seen.append(int(kwargs["timeout"]))
        return CompletedProcess([], 124, "", "")

    monkeypatch.setattr(test_runner, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(
        test_runner,
        "probe_runner_environment",
        lambda _: PytestCapabilities("python", "9", False),
    )
    monkeypatch.setattr(
        auditor, "get_rules_for_category", lambda *args, **kwargs: [TestCoverageRule()]
    )

    def check(timeout: int | None) -> None:
        kwargs = {} if timeout is None else {"test_timeout_seconds": timeout}
        verify_project(str(tmp_path), {"audit": AuditTool()}, **kwargs)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(check, [None, 3600]))
    assert sorted(seen) == [900, 3600]


@pytest.mark.parametrize("budget", [True, 0, -1, 86401])
def test_invalid_audit_budget_is_rejected(tmp_path: Path, budget: object) -> None:
    result = AuditTool().execute(path=str(tmp_path), test_timeout_seconds=budget)
    assert not result.success


def test_verify_does_not_send_test_budget_to_governance(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []

    class Instrument(AXMTool):
        @property
        def name(self) -> str:
            return "instrument"

        def execute(self, **kwargs: object) -> ToolResult:
            seen.append(kwargs)
            return ToolResult(success=True, data={})

    verify_project(
        str(tmp_path),
        {"audit": Instrument(), "init_check": Instrument()},
        test_timeout_seconds=3600,
    )
    assert seen == [
        {"path": str(tmp_path), "test_timeout_seconds": 3600},
        {"path": str(tmp_path)},
    ]


def test_precomputed_report_never_runs_tests_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-package"\nversion = "0.0.1"\n'
    )
    monkeypatch.setattr(
        auditor, "get_rules_for_category", lambda *args, **kwargs: [TestCoverageRule()]
    )

    def unexpected(*args: object, **kwargs: object) -> object:
        raise AssertionError("test subprocess called twice")

    monkeypatch.setattr(test_runner, "run_pytest", unexpected)
    report = test_runner.TestReport(
        timed_out=True, pytest_return_code=124, collected=0, verdict=False
    )
    result = auditor.audit_project(
        tmp_path, test_reports={tmp_path.resolve(): report}, test_timeout_seconds=3600
    )
    assert len(result.checks) == 1
    assert result.checks[0].details["timed_out"] is True
