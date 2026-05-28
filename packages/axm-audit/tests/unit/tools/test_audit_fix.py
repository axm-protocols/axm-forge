"""Unit tests for AuditFixTool MCP tool (AXM-1750).

In-memory only. The pipeline ``run`` is mocked so this module does not
touch the filesystem beyond the pytest-managed ``tmp_path``.
"""

from __future__ import annotations

import importlib.metadata

from axm_audit.tools.audit_fix import AuditFixTool


class TestAuditFixToolName:
    """AC1: tool exposes the ``audit_fix`` registry name."""

    def test_name_property_returns_audit_fix(self) -> None:
        """AC1: AuditFixTool().name == 'audit_fix'."""
        assert AuditFixTool().name == "audit_fix"


class TestAuditFixToolInvalidPath:
    """AC4: bad path returns an error ToolResult, never raises."""

    def test_execute_invalid_path_returns_error_result(self) -> None:
        """AC4: execute on a non-existent path returns success=False."""
        result = AuditFixTool().execute(path="/nonexistent/path/xyz-axm-1750")

        assert result.success is False
        assert result.error is not None
        assert "Not a directory" in result.error


def test_axm_tools_entry_point_resolves_audit_fix() -> None:
    """AC7: 'audit_fix' is registered in the axm.tools entry-point group."""
    eps = importlib.metadata.entry_points(group="axm.tools")
    names = {ep.name for ep in eps}

    assert "audit_fix" in names, (
        "audit_fix entry point not registered; re-run `uv sync` or "
        "`uv pip install -e .` after editing pyproject.toml"
    )

    audit_fix_ep = next(ep for ep in eps if ep.name == "audit_fix")
    loaded = audit_fix_ep.load()
    assert loaded is AuditFixTool
