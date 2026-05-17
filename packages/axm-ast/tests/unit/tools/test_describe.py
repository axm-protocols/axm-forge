"""Unit tests for DescribeTool — pure (no I/O)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture()
def tool() -> DescribeTool:
    """Provide a fresh DescribeTool instance."""
    return DescribeTool()


class TestDescribeToolIdentity:
    """Basic tool identity tests."""

    def test_name(self, tool: DescribeTool) -> None:
        assert tool.name == "ast_describe"

    def test_has_agent_hint(self, tool: DescribeTool) -> None:
        assert tool.agent_hint


class TestDescribeToolBadPath:
    """Bad path edge case (no filesystem I/O)."""

    def test_bad_path(self, tool: DescribeTool) -> None:
        result = tool.execute(path="/nonexistent/path/xyz")
        assert result.success is False


def test_describe_full_rejected():
    """detail='full' must be rejected with a clear error."""
    result = DescribeTool().execute(detail="full")

    assert result.success is False
    assert result.error is not None
    assert "detailed" in result.error.lower()
    assert "ast_inspect" in result.error.lower()


def test_describe_detailed_still_works(tmp_path, mocker):
    """detail='detailed' must still work and return modules."""
    pkg = MagicMock()
    pkg.modules = [MagicMock(), MagicMock()]

    mocker.patch(
        "axm_ast.core.cache.get_package",
        return_value=pkg,
    )
    mocker.patch(
        "axm_ast.formatters.filter_modules",
        return_value=pkg,
    )
    mocker.patch(
        "axm_ast.formatters.format_json",
        return_value={"modules": [{"name": "a"}, {"name": "b"}]},
    )

    result = DescribeTool().execute(path=str(tmp_path), detail="detailed")

    assert result.success is True
    assert result.data["module_count"] == 2
    assert len(result.data["modules"]) == 2
