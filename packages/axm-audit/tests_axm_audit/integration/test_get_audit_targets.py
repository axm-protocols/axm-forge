from __future__ import annotations

from pathlib import Path

from axm_audit.core.rules.quality_rules import _get_audit_targets


def test_get_audit_targets_includes_namespaced_suite(tmp_path: Path) -> None:
    """Mypy receives the resolved suite instead of a missing tests/ path."""
    project = tmp_path / "sample-pkg"
    src = project / "src"
    suite = project / "tests_sample_pkg"
    src.mkdir(parents=True)
    suite.mkdir()

    targets, checked = _get_audit_targets(project)

    assert targets == [str(src), str(suite)]
    assert checked == "src/ tests_sample_pkg/"
