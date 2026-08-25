from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.models.results import CheckResult


class _SyntheticRule(ProjectRule):
    rule_id = "synthetic.rule"
    description = "synthetic"

    def check(self, project_path: Path) -> CheckResult:  # pragma: no cover - unused
        return CheckResult(rule_id=self.rule_id, passed=True, message="ok")


def test_check_src_emits_typed_score(tmp_path: Path) -> None:
    rule = _SyntheticRule()
    result = rule.check_src(tmp_path)
    assert result is not None
    assert result.score == 100
    assert result.details is None or "score" not in result.details
