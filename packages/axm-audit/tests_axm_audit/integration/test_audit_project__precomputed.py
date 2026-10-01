"""Precomputed mode consumes suite evidence and refuses unavailable runners."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.coverage import TestCoverageRule as CoverageRule
from axm_audit.core.test_runner import TestReport as Report
from axm_audit.models.results import CheckResult


def test_precomputed_audit_never_executes_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = Mock(side_effect=AssertionError("pytest ran twice"))
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", runner)
    monkeypatch.setattr(
        "axm_audit.core.auditor.get_rules_for_category",
        lambda *a, **k: [CoverageRule()],
    )
    result = audit_project(
        tmp_path,
        test_reports={
            tmp_path.resolve(): Report(passed=1, coverage=100),
        },
    )
    assert result.checks[0].passed
    runner.assert_not_called()


def test_missing_precomputed_report_refuses_instead_of_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = Mock(side_effect=AssertionError("pytest ran twice"))
    monkeypatch.setattr("axm_audit.core.test_runner.run_tests", runner)
    monkeypatch.setattr(
        "axm_audit.core.auditor.get_rules_for_category",
        lambda *a, **k: [CoverageRule()],
    )
    result = audit_project(tmp_path, test_reports={})
    assert not result.checks[0].passed
    assert "missing precomputed" in result.checks[0].message
    runner.assert_not_called()


@pytest.mark.parametrize(
    "report",
    [
        Report(coverage=100),
        Report(passed=1, coverage=100, pytest_return_code=2),
        Report(passed=1, failed=1, coverage=100),
    ],
)
def test_invalid_suite_cannot_pass_with_green_coverage(
    tmp_path: Path, report: Report
) -> None:
    assert not CoverageRule().check_measured(tmp_path, report).passed


def test_future_suite_rule_without_consumer_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FutureRule(ProjectRule):
        runs_tests = True
        rule_id = "FUTURE_TESTS"

        def check(self, project_path: Path) -> CheckResult:
            raise AssertionError("a second suite execution is forbidden")

    monkeypatch.setattr(
        "axm_audit.core.auditor.get_rules_for_category",
        lambda *a, **k: [FutureRule()],
    )
    result = audit_project(
        tmp_path, test_reports={tmp_path.resolve(): Report(passed=1, coverage=100)}
    )
    assert not result.checks[0].passed
    assert "cannot consume precomputed tests" in result.checks[0].message
