"""Atomic file and directory write operations against a real filesystem."""

from __future__ import annotations

from pathlib import Path


class TestAtomicFileWrites:
    """write_file and create_dir succeed against a real filesystem."""

    def test_write_file_creates_file(self, tmp_path: Path) -> None:
        """write_file creates a new file with content."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()
        target = tmp_path / "test.txt"

        result = adapter.write_file(target, "Hello, World!")

        assert result is True
        assert target.exists()
        assert target.read_text() == "Hello, World!"

    def test_write_file_creates_parent_dirs(self, tmp_path: Path) -> None:
        """write_file creates parent directories if needed."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()
        target = tmp_path / "deep" / "nested" / "file.txt"

        result = adapter.write_file(target, "content")

        assert result is True
        assert target.exists()

    def test_create_dir_creates_directory(self, tmp_path: Path) -> None:
        """create_dir creates a new directory."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()
        target = tmp_path / "newdir"

        result = adapter.create_dir(target)

        assert result is True
        assert target.is_dir()

    def test_create_dir_nested(self, tmp_path: Path) -> None:
        """create_dir creates nested directories."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()
        target = tmp_path / "a" / "b" / "c"

        result = adapter.create_dir(target)

        assert result is True
        assert target.is_dir()
