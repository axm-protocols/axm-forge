"""Tests for axm_edit.tools.list_dir — ListDirTool."""

from __future__ import annotations

from axm_edit.tools import list_dir
from axm_edit.tools.list_dir import ListDirTool


class TestListDirTool:
    """Tests for the ListDirTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = ListDirTool()
        assert tool.name == "list_dir"

    def test_nonexistent_path(self) -> None:
        """Non-existent path returns an error."""
        result = ListDirTool().execute(path="/nonexistent/path/xyz_abc")
        assert result.success is False
        assert result.error is not None
        assert "not a directory" in result.error.lower()


def test_render_failure_text_preserves_path() -> None:
    """AC1: The failure rendering includes the input path verbatim."""
    path = "/x/pyproject.toml"
    error = f"Path is not a directory: {path}"

    text = list_dir.render_failure_text(path, error)

    assert text
    assert path in text


def test_render_failure_text_labels_failure_and_suggests_remedy() -> None:
    """AC2: The rendering labels the failure and gives one clear remedy."""
    path = "/x/pyproject.toml"
    error = f"Path is not a directory: {path}"

    text = list_dir.render_failure_text(path, error)
    lowered = text.lower()

    assert "not a directory" in lowered
    assert "read_file" in lowered or "pass a directory" in lowered
    assert lowered.count(error.lower()) == 1
