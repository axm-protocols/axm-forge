from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule

__all__: list[str] = []


@pytest.mark.integration
def test_known_false_positives_no_longer_reported() -> None:
    pkg_root = Path(__file__).resolve().parents[5]

    rule = PrivateImportsRule()
    result = rule.check(pkg_root)
    findings = result.details["findings"] if result.details else []

    known_false_positives = {
        ("tests/unit/core/rules/test_quality/test_pyramid_level_r4_r5.py", 16),
        ("tests/unit/core/rules/test_quality/test_shared.py", 283),
    }

    reported: set[tuple[str, int]] = set()
    for finding in findings:
        path = Path(finding["test_file"])
        try:
            rel = path.relative_to(pkg_root)
        except ValueError:
            rel = path
        rel_str = str(rel).replace("\\", "/")
        reported.add((rel_str, finding["line"]))

    leftover = reported & known_false_positives
    assert not leftover, f"Known false positives still reported: {leftover}"
