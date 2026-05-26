"""Tests for axm_edit.tools.list_dir — ListDirTool."""

from __future__ import annotations

from pathlib import Path

from axm_edit.tools.list_dir import ListDirTool


class TestListDirTool:
    """Tests for the ListDirTool AXMTool wrapper."""

    def test_name(self) -> None:
        tool = ListDirTool()
        assert tool.name == "list_dir"

    def test_list_root(self, tmp_project: Path) -> None:
        """Returns sorted entries from root directory."""
        result = ListDirTool().execute(path=str(tmp_project))
        assert result.success is True
        assert result.data is not None
        entries = result.data["entries"]
        names = [e["name"] for e in entries]
        # tmp_project has src/ and README.md
        assert "src" in names
        assert "README.md" in names
        # Sorted alphabetically
        assert names == sorted(names)

    def test_entry_shape(self, tmp_project: Path) -> None:
        """Each entry has name, path, type, and size_bytes fields."""
        result = ListDirTool().execute(path=str(tmp_project))
        assert result.success is True
        assert result.data is not None
        for entry in result.data["entries"]:
            assert "name" in entry
            assert "path" in entry
            assert "type" in entry
            assert entry["type"] in ("file", "dir")
            assert "size_bytes" in entry

    def test_depth_1_default(self, tmp_project: Path) -> None:
        """Default depth=1 does not recurse into subdirectories."""
        result = ListDirTool().execute(path=str(tmp_project))
        assert result.success is True
        assert result.data is not None
        paths = [e["path"] for e in result.data["entries"]]
        # foo.py is nested inside src/ — must not appear at depth=1
        assert not any("foo.py" in p for p in paths)

    def test_depth_2(self, tmp_project: Path) -> None:
        """max_depth=2 recurses one level into subdirectories."""
        result = ListDirTool().execute(path=str(tmp_project), max_depth=2)
        assert result.success is True
        assert result.data is not None
        paths = [e["path"] for e in result.data["entries"]]
        # foo.py and bar.py live in src/ — must appear with depth=2
        assert any("foo.py" in p for p in paths)
        assert any("bar.py" in p for p in paths)

    def test_skips_hidden(self, tmp_project: Path) -> None:
        """Hidden directories and files are not listed."""
        hidden = tmp_project / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("secret\n")
        result = ListDirTool().execute(path=str(tmp_project))
        assert result.success is True
        assert result.data is not None
        names = [e["name"] for e in result.data["entries"]]
        assert ".git" not in names

    def test_skips_pycache(self, tmp_project: Path) -> None:
        """__pycache__ directories are not listed."""
        cache = tmp_project / "src" / "__pycache__"
        cache.mkdir()
        (cache / "foo.cpython-312.pyc").write_text("CACHED\n")
        result = ListDirTool().execute(path=str(tmp_project), max_depth=2)
        assert result.success is True
        assert result.data is not None
        names = [e["name"] for e in result.data["entries"]]
        assert "__pycache__" not in names

    def test_result_cap(self, tmp_path: Path) -> None:
        """Results are capped at 200 entries."""
        for i in range(300):
            (tmp_path / f"file_{i:04d}.txt").write_text(f"content {i}\n")
        result = ListDirTool().execute(path=str(tmp_path))
        assert result.success is True
        assert result.data is not None
        assert result.data["count"] == 200
        assert result.data["truncated"] is True

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns success with an empty entries list."""
        result = ListDirTool().execute(path=str(tmp_path))
        assert result.success is True
        assert result.data is not None
        assert result.data["entries"] == []
        assert result.data["count"] == 0
        assert result.data["truncated"] is False

    def test_nonexistent_path(self) -> None:
        """Non-existent path returns an error."""
        result = ListDirTool().execute(path="/nonexistent/path/xyz_abc")
        assert result.success is False
        assert result.error is not None
        assert "not a directory" in result.error.lower()

    def test_path_traversal(self, tmp_path: Path) -> None:
        """Returned entry paths never contain '..'."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("safe\n")
        result = ListDirTool().execute(path=str(tmp_path), max_depth=2)
        assert result.success is True
        assert result.data is not None
        for entry in result.data["entries"]:
            assert ".." not in entry["path"]

    def test_file_size_bytes(self, tmp_path: Path) -> None:
        """Files include their size in bytes."""
        content = "hello world"
        (tmp_path / "test.txt").write_text(content)
        result = ListDirTool().execute(path=str(tmp_path))
        assert result.success is True
        assert result.data is not None
        file_entry = next(e for e in result.data["entries"] if e["name"] == "test.txt")
        assert file_entry["size_bytes"] == len(content.encode())

    def test_dir_size_bytes_is_none(self, tmp_path: Path) -> None:
        """Directories report size_bytes as None."""
        (tmp_path / "subdir").mkdir()
        result = ListDirTool().execute(path=str(tmp_path))
        assert result.success is True
        assert result.data is not None
        dir_entry = next(e for e in result.data["entries"] if e["name"] == "subdir")
        assert dir_entry["size_bytes"] is None
