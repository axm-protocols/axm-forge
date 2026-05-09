"""Unit tests for PyramidLevelRule (R1+R2+R3 soft-signal core)."""

from __future__ import annotations

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.pyramid_level import (
    PyramidLevelRule,
    classify_level,
)


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    classes = {item if isinstance(item, type) else type(item) for item in bucket}
    assert PyramidLevelRule in classes


@pytest.mark.parametrize(
    ("has_real_io", "has_subprocess", "imports_public", "imports_internal", "expected"),
    [
        (False, True, False, False, "e2e"),
        (True, True, True, True, "e2e"),
        (False, False, True, False, "unit"),
        (True, False, True, False, "integration"),
        (True, False, False, True, "integration"),
        (True, False, False, False, "integration"),
        (False, False, False, True, "unit"),
        (False, False, False, False, "unit"),
    ],
)
def test_classify_level_8_branches_table_driven(
    has_real_io: bool,
    has_subprocess: bool,
    imports_public: bool,
    imports_internal: bool,
    expected: str,
) -> None:
    level, reason = classify_level(
        has_real_io=has_real_io,
        has_subprocess=has_subprocess,
        imports_public=imports_public,
        imports_internal=imports_internal,
    )
    assert level == expected
    assert reason
