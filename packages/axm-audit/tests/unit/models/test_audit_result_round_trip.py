from __future__ import annotations

import pytest
from pydantic import ValidationError

from axm_audit.models.results import AuditResult, CheckResult


def _check(score: float, category: str = "lint", rule_id: str = "r1") -> CheckResult:
    return CheckResult(
        rule_id=rule_id,
        passed=True,
        message="ok",
        category=category,
        score=int(score),
    )


def test_audit_result_round_trip() -> None:
    ar = AuditResult(checks=[_check(88)])
    # Pure round-trip across the persistent (non-computed) fields: dump and
    # re-validate without the __init__ hack popping keys.
    dump = ar.model_dump(
        exclude={"success", "total", "failed", "quality_score", "grade"}
    )
    restored = AuditResult.model_validate(dump)
    assert restored == ar
    assert ar.quality_score == 88.0
    assert restored.quality_score == 88.0


def test_audit_result_quality_score_computed_from_checks() -> None:
    ar = AuditResult(checks=[_check(80, rule_id="r1"), _check(100, rule_id="r2")])
    assert ar.quality_score == 90.0


def test_audit_result_rejects_quality_score_kwarg() -> None:
    with pytest.raises(ValidationError):
        AuditResult(quality_score=85)  # type: ignore[call-arg]


def test_audit_result_rejects_grade_kwarg() -> None:
    with pytest.raises(ValidationError):
        AuditResult(grade="A")  # type: ignore[call-arg]


def test_audit_result_no_override_attrs_after_migration() -> None:
    private_attrs = AuditResult.__private_attributes__
    assert "_override_quality_score" not in private_attrs
    assert "_override_grade" not in private_attrs


def test_audit_result_empty_checks_quality_score_none() -> None:
    ar = AuditResult(checks=[])
    assert ar.quality_score is None
    assert ar.grade is None
