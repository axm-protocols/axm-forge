from __future__ import annotations

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsCheckResult,
)
from axm_audit.core.rules.test_quality.tautology import TautologyCheckResult
from axm_audit.formatters import format_agent, format_agent_text
from axm_audit.models.results import AuditResult, CheckResult


def _audit(checks: list[CheckResult]) -> AuditResult:
    return AuditResult(checks=checks)


def test_format_agent_failed_includes_metadata_when_present() -> None:
    verdicts = [
        {
            "file": "tests/unit/test_x.py",
            "test": "test_x",
            "line": 3,
            "pattern": "assert True",
            "verdict": "tautology",
            "reason": "trivially true",
        }
    ]
    check = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="1 tautological test",
        metadata={"verdicts": verdicts},
    )
    out = format_agent(_audit([check]))
    assert out["failed"][0]["metadata"]["verdicts"] == verdicts


def test_format_agent_passed_includes_metadata_when_present() -> None:
    check = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=True,
        message="ok",
        metadata={"verdicts": [{"info": 1}]},
    )
    out = format_agent(_audit([check]))
    entry = out["passed"][0]
    assert isinstance(entry, dict)
    assert entry["metadata"] == {"verdicts": [{"info": 1}]}


def test_format_agent_omits_metadata_when_empty() -> None:
    empty_meta = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="failed",
        metadata={},
    )
    no_meta = CheckResult(
        rule_id="OTHER",
        passed=False,
        message="failed",
    )
    out = format_agent(_audit([empty_meta, no_meta]))
    for entry in out["failed"]:
        assert "metadata" not in entry


def test_format_agent_clusters_metadata_propagates() -> None:
    clusters = [{"id": 0, "members": ["a", "b"]}]
    check = DuplicateTestsCheckResult(
        rule_id="TEST_QUALITY_DUPLICATE_TESTS",
        passed=False,
        message="1 duplicate cluster",
        metadata={"clusters": clusters},
    )
    out = format_agent(_audit([check]))
    assert out["failed"][0]["metadata"]["clusters"] == clusters


def test_format_agent_text_unchanged_for_tautology() -> None:
    verdicts = [
        {
            "file": "tests/unit/test_x.py",
            "test": "test_x",
            "line": 3,
            "pattern": "assert True",
            "verdict": "tautology",
            "reason": "trivially true",
        }
    ]
    dup = DuplicateTestsCheckResult(
        rule_id="TEST_QUALITY_DUPLICATE_TESTS",
        passed=False,
        message="dup",
        metadata={"clusters": [{"id": 0, "members": ["a", "b"]}]},
    )
    taut = TautologyCheckResult(
        rule_id="TEST_QUALITY_TAUTOLOGY",
        passed=False,
        message="taut",
        metadata={"verdicts": verdicts},
    )
    result = _audit([dup, taut])
    text = format_agent_text(format_agent(result))
    assert isinstance(text, str)
    assert text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
