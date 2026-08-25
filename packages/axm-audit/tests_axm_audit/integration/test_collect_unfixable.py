"""Split from ``test_findings.py``."""

from collections.abc import Callable
from pathlib import Path

from axm_audit.core.fix.findings import collect_unfixable


def test_collect_unfixable_surfaces_no_package_symbol(
    make_pkg: Callable[..., Path],
) -> None:
    """AC4: surfaces TEST_QUALITY_NO_PACKAGE_SYMBOL (NON_DETERMINISTIC_RULES)."""
    pkg = make_pkg(
        files={
            "tests/integration/test_x.py": (
                "def test_x() -> None:\n    assert 1 == 1\n"
            ),
        }
    )
    result = collect_unfixable(pkg)
    assert any(f.get("rule_id") == "TEST_QUALITY_NO_PACKAGE_SYMBOL" for f in result)
