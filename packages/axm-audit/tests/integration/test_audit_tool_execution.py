"""Integration tests for AuditTool execution against real project layouts."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_execute_valid_project(tmp_path: Path) -> None:
    """AuditTool on a valid project returns success with data."""
    from axm_audit.tools.audit import AuditTool

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        'name = "test-pkg"\n'
        'version = "0.1.0"\n'
        'description = "Test"\n'
        'requires-python = ">=3.12"\n'
    )

    tool = AuditTool()
    result = tool.execute(path=str(tmp_path))

    assert result.success is True
    assert result.data is not None
    assert "score" in result.data
    assert "grade" in result.data


def test_execute_not_a_directory(tmp_path: Path) -> None:
    """AuditTool on a non-directory path returns failure."""
    from axm_audit.tools.audit import AuditTool

    fake_path = tmp_path / "nonexistent"

    tool = AuditTool()
    result = tool.execute(path=str(fake_path))

    assert result.success is False
    assert result.error is not None
    assert "Not a directory" in result.error


def test_execute_with_category_filter(tmp_path: Path) -> None:
    """AuditTool with category filter runs only that category."""
    from axm_audit.tools.audit import AuditTool

    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text('"""Package."""\n')
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
    )

    tool = AuditTool()
    result = tool.execute(path=str(tmp_path), category="structure")

    assert result.success is True
    assert result.data is not None
