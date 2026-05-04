from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from axm_audit.models.results import CheckResult, _collect_category_scores


def test_check_result_has_typed_score() -> None:
    result = CheckResult(rule_id="r", passed=True, message="ok", score=85)
    assert result.score == 85
    assert isinstance(result.score, int)


def test_check_result_score_validation() -> None:
    with pytest.raises(ValidationError):
        CheckResult(rule_id="r", passed=True, message="ok", score=150)
    with pytest.raises(ValidationError):
        CheckResult(rule_id="r", passed=True, message="ok", score=-1)


def test_check_result_score_default_none() -> None:
    result = CheckResult(rule_id="r", passed=True, message="ok")
    assert result.score is None


def test_collect_category_scores_reads_typed_score() -> None:
    check = CheckResult(
        rule_id="r", passed=True, message="ok", category="lint", score=80
    )
    assert _collect_category_scores([check]) == {"lint": [80.0]}


def test_collect_category_scores_warns_on_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    check = CheckResult(
        rule_id="my_rule", passed=True, message="ok", category="lint", score=None
    )
    with caplog.at_level(logging.WARNING):
        result = _collect_category_scores([check])
    assert result == {}
    assert any(
        record.levelno == logging.WARNING and "my_rule" in record.getMessage()
        for record in caplog.records
    )


def test_collect_category_scores_no_warn_for_unscored_category(
    caplog: pytest.LogCaptureFixture,
) -> None:
    check = CheckResult(
        rule_id="r", passed=True, message="ok", category="structure", score=None
    )
    with caplog.at_level(logging.WARNING):
        _collect_category_scores([check])
    assert not any(record.levelno == logging.WARNING for record in caplog.records)
