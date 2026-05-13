"""Unit tests for format_flow_compact (split from tests/test_flows_refactor.py)."""

from __future__ import annotations

from axm_ast.core.flows import FlowStep, format_flow_compact


class TestFormatFlowCompact:
    """Unit tests for format_flow_compact."""

    def test_empty_steps_returns_empty_string(self) -> None:
        assert format_flow_compact([]) == ""

    def test_single_root_step(self) -> None:
        steps = [
            FlowStep(name="main", module="pkg.main", line=10, depth=0, chain=["main"]),
        ]
        result = format_flow_compact(steps)
        assert "main" in result
        assert "pkg.main:10" in result

    def test_nested_steps_use_connectors(self) -> None:
        steps = [
            FlowStep(name="root", module="m", line=1, depth=0, chain=["root"]),
            FlowStep(
                name="child",
                module="m",
                line=5,
                depth=1,
                chain=["root", "child"],
            ),
        ]
        result = format_flow_compact(steps)
        lines = result.splitlines()
        assert len(lines) == 2
        # Child line should have a connector
        assert "└──" in lines[1] or "├──" in lines[1]

    def test_resolved_module_shown(self) -> None:
        steps = [
            FlowStep(
                name="func",
                module="a.b",
                line=1,
                depth=0,
                chain=["func"],
                resolved_module="x.y",
            ),
        ]
        result = format_flow_compact(steps)
        assert "→ x.y" in result
