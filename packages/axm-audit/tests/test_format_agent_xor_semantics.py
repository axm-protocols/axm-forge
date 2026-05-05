from __future__ import annotations

from typing import Any

import pytest

from axm_audit.formatters import format_agent
from axm_audit.models import AuditResult, CheckResult


def _make_result(*checks: CheckResult) -> AuditResult:
    return AuditResult(checks=list(checks))


@pytest.mark.parametrize(
    ("text", "details", "expected_text", "expected_details"),
    [
        pytest.param(
            "• issue",
            {"items": [1]},
            "• issue",
            None,
            id="text_wins_over_details",
        ),
        pytest.param(
            None,
            {"items": [1]},
            None,
            {"items": [1]},
            id="none_text_falls_back_to_details",
        ),
        pytest.param(
            "",
            {"items": [1]},
            None,
            {"items": [1]},
            id="empty_text_falls_back_to_details",
        ),
        pytest.param(None, None, None, None, id="both_none_emits_neither"),
        pytest.param("• issue", None, "• issue", None, id="text_only"),
        pytest.param(None, {}, None, {}, id="empty_details_dict_still_emitted"),
    ],
)
def test_format_agent_text_details_xor(
    text: str | None,
    details: dict[str, Any] | None,
    expected_text: str | None,
    expected_details: dict[str, Any] | None,
) -> None:
    """format_agent emits text XOR details on failed checks (text wins when truthy)."""
    cr = CheckResult(rule_id="R", message="m", passed=False, text=text, details=details)
    entry = format_agent(_make_result(cr))["failed"][0]

    if expected_text is None:
        assert "text" not in entry
    else:
        assert entry["text"] == expected_text

    if expected_details is None:
        assert "details" not in entry
    else:
        assert entry["details"] == expected_details
