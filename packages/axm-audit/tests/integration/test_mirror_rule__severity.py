"""Split from ``test_practices.py``."""

from pathlib import Path

from axm_audit.models.results import Severity


def test_no_src_directory(tmp_path: Path) -> None:
    """Empty project without src/ should pass with INFO."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True
    assert result.severity == Severity.INFO
