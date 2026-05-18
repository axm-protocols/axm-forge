"""Split from ``test_tautology_detect.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality.tautology import TautologyRule
from axm_audit.models.results import Severity


def test_severity_warning(tmp_path: Path) -> None:
    f = tmp_path / "test_sample.py"
    f.write_text("def test_foo():\n    assert True\n")
    rule = TautologyRule()
    result = rule.check(tmp_path)
    assert result.severity == Severity.WARNING
