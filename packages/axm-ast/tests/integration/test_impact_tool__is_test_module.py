"""Split from ``test_impact_test_filter.py``."""

from pathlib import Path

from axm_ast.core.impact import _is_test_module
from tests.integration._helpers import (
    _make_project_with_test_callers__from_impact_test_filter,
)


def test_impact_mcp_test_filter_param(tmp_path: Path) -> None:
    """MCP tool accepts test_filter param and returns filtered results."""
    from axm_ast.tools.impact import ImpactTool

    pkg = _make_project_with_test_callers__from_impact_test_filter(tmp_path)
    tool = ImpactTool()
    result = tool.execute(
        path=str(pkg),
        symbol="target_fn",
        test_filter="related",
    )
    assert result.success
    test_callers = [c for c in result.data["callers"] if _is_test_module(c["module"])]
    test_modules = {c["module"] for c in test_callers}
    assert any("test_a" in m for m in test_modules)
    assert not any("test_b" in m for m in test_modules)
