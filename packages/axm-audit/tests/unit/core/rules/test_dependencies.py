from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.dependencies import DependencyAuditRule

MODULE = "axm_audit.core.rules.dependencies"


@pytest.fixture
def rule() -> DependencyAuditRule:
    return DependencyAuditRule()


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    return tmp_path


def _patch_audit(mocker: Any, payload: list[dict[str, Any]]) -> None:
    mocker.patch(f"{MODULE}._run_pip_audit", return_value=payload)


def test_check_excludes_pip_env_tool(
    mocker: Any, rule: DependencyAuditRule, project_path: Path
) -> None:
    _patch_audit(
        mocker,
        [
            {
                "name": "pip",
                "version": "26.0.1",
                "vulns": [{"id": "CVE-2026-3219", "fix_versions": []}],
            }
        ],
    )

    result = rule.check(project_path)

    assert result.details is not None
    assert result.details["vuln_count"] == 0
    assert result.passed is True
    assert result.details["top_vulns"] == []


def test_check_keeps_real_vuln_alongside_env_tool(
    mocker: Any, rule: DependencyAuditRule, project_path: Path
) -> None:
    _patch_audit(
        mocker,
        [
            {
                "name": "pip",
                "version": "26.0.1",
                "vulns": [{"id": "CVE-2026-3219", "fix_versions": []}],
            },
            {
                "name": "requests",
                "version": "2.20.0",
                "vulns": [{"id": "CVE-2018-18074", "fix_versions": ["2.20.1"]}],
            },
        ],
    )

    result = rule.check(project_path)

    assert result.details is not None
    assert result.details["vuln_count"] == 1
    assert result.details["top_vulns"][0]["name"] == "requests"


@pytest.mark.parametrize(
    "pkg_name",
    ["pip", "setuptools", "wheel", "uv", "pip-audit", "PIP", "Setuptools"],
)
def test_check_excludes_each_env_tool(
    mocker: Any,
    rule: DependencyAuditRule,
    project_path: Path,
    pkg_name: str,
) -> None:
    _patch_audit(
        mocker,
        [
            {
                "name": pkg_name,
                "version": "1.0.0",
                "vulns": [{"id": "CVE-XXXX-0001", "fix_versions": []}],
            }
        ],
    )

    result = rule.check(project_path)

    assert result.details is not None
    assert result.details["vuln_count"] == 0


def test_check_passes_through_unknown_package(
    mocker: Any, rule: DependencyAuditRule, project_path: Path
) -> None:
    _patch_audit(
        mocker,
        [
            {
                "name": "numpy",
                "version": "1.0.0",
                "vulns": [{"id": "CVE-XXXX-0002", "fix_versions": []}],
            }
        ],
    )

    result = rule.check(project_path)

    assert result.details is not None
    assert result.details["vuln_count"] == 1
