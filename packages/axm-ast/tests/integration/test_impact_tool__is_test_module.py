"""Drive ``_is_test_module`` filter through public :class:`ImpactTool` MCP entrypoint.

Mirrors the ``test_filter='related'`` direct-only behavior asserted at the
function level in ``test_analyze_impact__is_test_module.py``, but verifies
that the MCP tool layer (``ImpactTool.execute``) forwards the parameter
and exposes the same filtered ``callers`` payload via its public ``result.data``.
"""

from pathlib import Path

from tests.integration._helpers import (
    _make_project_with_test_callers__from_impact_test_filter,
)


def _is_test_module_name(module: str) -> bool:
    """Local mirror of the public classification rule for assertion purposes."""
    parts = module.split(".")
    return any(p.startswith("test_") or p == "tests" for p in parts)


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
    test_callers = [
        c for c in result.data["callers"] if _is_test_module_name(c["module"])
    ]
    test_modules = {c["module"] for c in test_callers}
    assert any("test_a" in m for m in test_modules)
    assert not any("test_b" in m for m in test_modules)
