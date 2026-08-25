"""Unit tests for dependency text format helpers (deptry label mapping)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from axm_audit.core.rules import dependencies
from axm_audit.core.rules.dependencies import (
    _DEPTRY_LABELS,
    PASS_THRESHOLD,
    DependencyAuditRule,
)
from axm_audit.models.results import Severity


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_command_includes_skip_editable(mocker):
    """AC1: the pip-audit invocation passes `--skip-editable`."""
    run = mocker.patch.object(
        dependencies, "run_in_project", return_value=_completed(0, stdout="[]")
    )

    DependencyAuditRule().check(Path("."))

    cmd = run.call_args.args[0]
    assert "--skip-editable" in cmd


def test_service_error_maps_to_skip(mocker):
    """AC2: a transient pypi ServiceError/503 is surfaced as a non-penalizing SKIP."""
    mocker.patch.object(
        dependencies,
        "run_in_project",
        return_value=_completed(
            1,
            stderr=(
                "pip_audit._service.interface.ServiceError\n"
                "503 Server Error: Backend is unhealthy"
            ),
        ),
    )

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is True
    assert result.severity is Severity.WARNING
    assert result.score >= PASS_THRESHOLD
    assert "skip" in result.message.lower() or "unreachable" in result.message.lower()


def test_timeout_rc124_maps_to_skip(mocker):
    """AC2: a `run_in_project` timeout (rc=124) maps to a non-penalizing SKIP."""
    mocker.patch.object(
        dependencies,
        "run_in_project",
        return_value=_completed(124, stderr="Command timed out after 300s"),
    )

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is True
    assert result.severity is Severity.WARNING
    assert result.score >= PASS_THRESHOLD


def test_real_vuln_still_fails(mocker):
    """AC3: a real vulnerability on a published external dep is still detected."""
    stdout = (
        '{"dependencies": [{"name": "requests", "version": "2.0.0", '
        '"vulns": [{"id": "PYSEC-2099-1", "fix_versions": ["2.31.0"], '
        '"description": "bad"}]}]}'
    )
    mocker.patch.object(
        dependencies, "run_in_project", return_value=_completed(0, stdout=stdout)
    )

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is False
    assert result.details["vuln_count"] == 1


def test_clean_audit_passes(mocker):
    """AC3: a clean audit passes with no vulnerabilities."""
    mocker.patch.object(
        dependencies, "run_in_project", return_value=_completed(0, stdout="[]")
    )

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is True
    assert result.details["vuln_count"] == 0
    assert "No known vulnerabilities" in result.message


def test_pip_audit_missing_is_error_fail(mocker):
    """AC4: pip-audit missing (FileNotFoundError) stays a distinct ERROR fail."""
    mocker.patch.object(dependencies, "run_in_project", side_effect=FileNotFoundError)

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is False
    assert result.severity is Severity.ERROR
    assert "pip-audit not available" in result.message


def test_non_network_failure_is_not_skipped(mocker):
    """AC4: a non-network pip-audit failure is not silently skipped (ERROR fail)."""
    mocker.patch.object(
        dependencies,
        "run_in_project",
        return_value=_completed(1, stdout="", stderr="some unrelated crash"),
    )

    result = DependencyAuditRule().check(Path("."))

    assert result.passed is False
    assert result.severity is Severity.ERROR


class TestUnitScope:
    def test_deptry_labels_known_codes(self):
        expected = {
            "DEP001": "missing dep",
            "DEP002": "unused dep",
            "DEP003": "transitive dep",
            "DEP004": "misplaced dev dep",
        }
        for code, label in expected.items():
            assert _DEPTRY_LABELS.get(code) == label, f"{code} should map to {label!r}"

    def test_deptry_labels_unknown_fallback(self):
        assert _DEPTRY_LABELS.get("DEP999", "original msg") == "original msg"
