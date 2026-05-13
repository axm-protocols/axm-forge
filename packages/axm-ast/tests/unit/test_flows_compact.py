"""Unit tests for compact output mode in ast_flows (AXM-939)."""

from __future__ import annotations

from axm_ast.core.flows import FlowStep


def _step(
    name: str, module: str, line: int, depth: int, chain: list[str] | None = None
) -> FlowStep:
    """Create a FlowStep with defaults."""
    return FlowStep(
        name=name,
        module=module,
        line=line,
        depth=depth,
        chain=chain or [],
    )


class TestFormatFlowCompactSingleDepth:
    """3 FlowSteps at depth 0, 1, 1 → tree with root + 2 children."""

    def test_format_flow_compact_single_depth(self) -> None:
        steps = [
            _step("main", "mod", 1, 0),
            _step("caller", "mod", 5, 1),
            _step("helper", "mod", 10, 1),
        ]
        result = _format_compact(steps)
        assert "main" in result
        assert "caller" in result
        assert "helper" in result
        # Root at depth 0 has no indent, children at depth 1 have tree chars
        lines = result.strip().splitlines()
        assert lines[0].strip() == "main  (mod:1)"
        # Children should use box-drawing characters
        assert any("├" in line or "└" in line for line in lines[1:])


class TestFormatFlowCompactNested:
    """Steps at depth 0, 1, 2, 1 → proper indentation with box-drawing chars."""

    def test_format_flow_compact_nested(self) -> None:
        steps = [
            _step("main", "mod", 1, 0),
            _step("caller", "mod", 5, 1),
            _step("deep", "mod", 8, 2),
            _step("other", "mod", 12, 1),
        ]
        result = _format_compact(steps)
        lines = result.strip().splitlines()
        # Should have 4 lines (one per step)
        assert len(lines) == 4
        # Depth-2 node should be more indented than depth-1 nodes
        depth1_indent = len(lines[1]) - len(lines[1].lstrip())
        depth2_indent = len(lines[2]) - len(lines[2].lstrip())
        assert depth2_indent > depth1_indent


class TestFormatFlowCompactEmpty:
    """Empty step list → empty string or 'No flows traced'."""

    def test_format_flow_compact_empty(self) -> None:
        result = _format_compact([])
        assert result == "" or "No flows" in result


class TestCompactExcludesChain:
    """Steps with chain populated → output contains no chain data."""

    def test_compact_excludes_chain(self) -> None:
        steps = [
            _step("main", "mod", 1, 0, chain=["main"]),
            _step("caller", "mod", 5, 1, chain=["main", "caller"]),
            _step("helper", "mod", 10, 2, chain=["main", "caller", "helper"]),
        ]
        result = _format_compact(steps)
        # Chain paths should not appear in compact output
        assert "['main'" not in result
        assert "main, caller" not in result
        # But symbol names should still appear
        assert "main" in result
        assert "caller" in result


def _format_compact(steps: list[FlowStep]) -> str:
    """Lazy import of format_flow_compact (not yet implemented)."""
    from axm_ast.core.flows import format_flow_compact

    return format_flow_compact(steps)
