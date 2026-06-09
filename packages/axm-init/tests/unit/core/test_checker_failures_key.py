"""Unit tests for the harmonized failures key in machine serializers.

AC1/AC2: ``format_json`` and ``format_agent`` must emit the failed-checks
list under the SAME canonical top-level key ``"failures"`` (matching the
source field ``ProjectResult.failures``) and never under ``"failed"``.
"""

from __future__ import annotations

from pathlib import Path

from axm_init.core.checker import format_agent, format_json
from axm_init.models.check import CheckResult, ProjectResult


def _result_with_failure() -> ProjectResult:
    """Build an in-memory ProjectResult carrying exactly one failed check."""
    failing = CheckResult(
        name="has_license",
        category="structure",
        passed=False,
        weight=5,
        message="LICENSE file missing",
        details=["expected LICENSE at project root"],
        fix="add a LICENSE file",
    )
    return ProjectResult.from_checks(Path("/tmp/project"), [failing])


def test_json_and_agent_use_same_failures_key() -> None:
    """AC1/AC2: both serializers expose failures under ``"failures"``."""
    result = _result_with_failure()

    json_out = format_json(result)
    agent_out = format_agent(result)

    # Canonical key present in both.
    assert "failures" in json_out
    assert "failures" in agent_out

    # The divergent legacy key is absent from both.
    assert "failed" not in json_out
    assert "failed" not in agent_out

    # Both carry the single failed check under the canonical key.
    assert len(json_out["failures"]) == 1
    assert len(agent_out["failures"]) == 1
    assert json_out["failures"][0]["name"] == "has_license"
    assert agent_out["failures"][0]["name"] == "has_license"
