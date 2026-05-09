from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.core.rules.dependencies import DependencyAuditRule
from axm_audit.models.results import CheckResult

MODULE = "axm_audit.core.rules.dependencies"


@pytest.fixture
def rule() -> DependencyAuditRule:
    return DependencyAuditRule()


def _vuln(name: str, version: str, vulns: list[dict[str, object]]) -> dict[str, object]:
    return {"name": name, "version": version, "vulns": vulns}


def _entry(cve_id: str, fix_versions: list[str] | None = None) -> dict[str, object]:
    return {"id": cve_id, "fix_versions": fix_versions or []}


def _check_with_vulns(
    rule: DependencyAuditRule, tmp_path: Path, raw_vulns: list[dict[str, object]]
) -> CheckResult:
    with (
        patch(f"{MODULE}._run_pip_audit", return_value=[]),
        patch(f"{MODULE}._parse_vulns", return_value=raw_vulns),
    ):
        return rule.check(tmp_path)


# --- Unit tests ---


def test_deps_audit_text_single_cve(rule: DependencyAuditRule, tmp_path: Path) -> None:
    raw = [_vuln("requests", "2.28.0", [_entry("CVE-2023-32681", ["2.31.0"])])]
    result = _check_with_vulns(rule, tmp_path, raw)
    assert result.text == "\u2022 requests 2.28.0\u21922.31.0 CVE-2023-32681"


@pytest.mark.parametrize(
    ("raw", "expected_substring"),
    [
        pytest.param(
            [
                _vuln(
                    "requests",
                    "2.28.0",
                    [
                        _entry("CVE-2023-32681", ["2.31.0"]),
                        _entry("CVE-2023-99999", ["2.31.0"]),
                    ],
                )
            ],
            "+1",
            id="multi_cve",
        ),
        pytest.param(
            [_vuln("pkg", "1.0.0", [_entry("CVE-2024-0001")])],
            "\u2192?",
            id="no_fix",
        ),
        pytest.param(
            [
                _vuln(
                    "pkg",
                    "1.0.0",
                    [
                        _entry("CVE-2024-0001", ["2.0"]),
                        _entry("CVE-2024-0002", ["2.1"]),
                    ],
                )
            ],
            "\u21922.0,2.1",
            id="multiple_fix_versions",
        ),
        pytest.param(
            [_vuln("pkg", "1.0.0", [])],
            "pkg",
            id="empty_vuln_ids",
        ),
    ],
)
def test_deps_audit_text_substring(
    rule: DependencyAuditRule,
    tmp_path: Path,
    raw: list[dict[str, object]],
    expected_substring: str,
) -> None:
    result = _check_with_vulns(rule, tmp_path, raw)
    assert result.text is not None
    assert expected_substring in result.text


def test_deps_audit_text_passed(rule: DependencyAuditRule, tmp_path: Path) -> None:
    result = _check_with_vulns(rule, tmp_path, [])
    assert result.text is None


# --- Edge cases ---


def test_deps_audit_text_top_vulns_cap(
    rule: DependencyAuditRule, tmp_path: Path
) -> None:
    raw = [
        _vuln(f"pkg{i}", "1.0.0", [_entry(f"CVE-2024-{i:04d}", ["2.0"])])
        for i in range(7)
    ]
    result = _check_with_vulns(rule, tmp_path, raw)
    assert result.text is not None
    lines = result.text.strip().split("\n")
    assert len(lines) == 5


def test_deps_audit_text_details_unchanged(
    rule: DependencyAuditRule, tmp_path: Path
) -> None:
    raw = [_vuln("requests", "2.28.0", [_entry("CVE-2023-32681", ["2.31.0"])])]
    result = _check_with_vulns(rule, tmp_path, raw)
    assert result.details is not None
    assert result.details["vuln_count"] == 1
    assert result.score == 85
    assert len(result.details["top_vulns"]) == 1
    vuln = result.details["top_vulns"][0]
    assert vuln["name"] == "requests"
    assert vuln["version"] == "2.28.0"
    assert vuln["vuln_ids"] == ["CVE-2023-32681"]
    assert vuln["fix_versions"] == ["2.31.0"]
