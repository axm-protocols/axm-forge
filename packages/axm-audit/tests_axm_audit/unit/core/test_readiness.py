"""Readiness distinguishes unavailable instruments from code findings."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.core.readiness import validation_readiness


@pytest.fixture(autouse=True)
def fake_project(full_pytest_environment: None):
    with (
        patch(
            "axm_audit.core.rules.quality_rules.LintingRule.check_src",
            return_value=None,
        ),
        patch("axm_audit.core.readiness.tempfile.TemporaryDirectory") as directory,
    ):
        directory.return_value.__enter__.return_value = "/reports"
        yield


@pytest.mark.parametrize("code", [0, 1, 2, 4, 124])
def test_collection_failure_never_passes(code: int) -> None:
    with (
        patch(
            "axm_audit.core.rules.quality_rules._get_audit_targets",
            return_value=(["src"], "src/"),
        ),
        patch(
            "axm_audit.core.readiness.run_pytest",
            return_value=subprocess.CompletedProcess([], code, "", "collection cause"),
        ),
        patch(
            "axm_audit.core.readiness.run_in_project",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        failures = validation_readiness(Path("/package"))
    assert ("pytest" in failures) == (code != 0)
    if code:
        assert "collection cause" in failures["pytest"]


def test_no_source_layout_skips_the_same_quality_gates() -> None:
    with (
        patch(
            "axm_audit.core.rules.quality_rules.LintingRule.check_src",
            return_value=object(),
        ),
        patch(
            "axm_audit.core.rules.quality_rules._get_audit_targets",
            return_value=([], ""),
        ),
        patch(
            "axm_audit.core.readiness.run_pytest",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
        patch("axm_audit.core.readiness.run_in_project") as tools,
    ):
        assert validation_readiness(Path("/package")) == {}
    tools.assert_not_called()


def test_code_findings_do_not_refuse_a_runnable_lane() -> None:
    with (
        patch(
            "axm_audit.core.rules.quality_rules._get_audit_targets",
            return_value=(["src"], "src/"),
        ),
        patch(
            "axm_audit.core.readiness.run_pytest",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ) as tests,
        patch(
            "axm_audit.core.readiness.run_in_project",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ) as tools,
    ):
        assert validation_readiness(Path("/package")) == {}
    assert "--collect-only" in tests.call_args.args[0]
    assert tools.call_args_list[0].args[0] == [
        "ruff",
        "check",
        "--output-format=json",
        "src",
    ]
    assert tools.call_args_list[1].args[0] == [
        "mypy",
        "--no-error-summary",
        "--output",
        "json",
        "src",
    ]
