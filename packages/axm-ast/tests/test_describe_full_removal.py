from __future__ import annotations

import pytest

from axm_ast.tools.describe import DescribeTool


@pytest.fixture()
def tool() -> DescribeTool:
    return DescribeTool()


@pytest.fixture()
def demo_pkg(tmp_path):
    """Create a minimal Python package for integration tests."""
    pkg = tmp_path / "demo_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Demo package."""\n')
    (pkg / "core.py").write_text(
        '"""Core module."""\n\n\ndef hello(name: str) -> str:\n'
        '    """Say hello."""\n    return f"Hello, {name}"\n'
    )
    return pkg


class TestDescribeDetailedStillWorks:
    """detail='detailed' must continue to work."""

    def test_describe_detailed_still_works(self, tool, demo_pkg):
        result = tool.execute(path=str(demo_pkg), detail="detailed")
        assert result.success is True
        assert result.data["module_count"] >= 1


class TestDescribeSummaryDefault:
    """Default detail level is 'summary'."""

    def test_describe_summary_default(self, tool, demo_pkg):
        result = tool.execute(path=str(demo_pkg))
        assert result.success is True
        assert result.data["module_count"] >= 1
