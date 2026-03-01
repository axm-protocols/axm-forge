"""Tests for FileSystemAdapter — RED phase."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest


class TestFileSystemAdapter:
    """Tests for atomic filesystem operations."""

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


class TestTransaction:
    """Tests for atomic transaction support."""

    def test_transaction_commits_on_success(self, tmp_path: Path) -> None:
        """Successful transaction keeps all files."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()

        with adapter.transaction() as tx:
            tx.write_file(tmp_path / "a.txt", "A")
            tx.write_file(tmp_path / "b.txt", "B")

        assert (tmp_path / "a.txt").exists()
        assert (tmp_path / "b.txt").exists()

    def test_transaction_rollback_on_error(self, tmp_path: Path) -> None:
        """Failed transaction removes created files."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()

        try:
            with adapter.transaction() as tx:
                tx.write_file(tmp_path / "keep.txt", "data")
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        # File should be rolled back
        assert not (tmp_path / "keep.txt").exists()

    def test_transaction_tracks_created_files(self, tmp_path: Path) -> None:
        """Transaction tracks files for rollback."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()

        with adapter.transaction() as tx:
            tx.write_file(tmp_path / "tracked.txt", "data")
            assert len(tx.created_files) == 1

    def test_rollback_logs_on_unlink_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Rollback logs warning when file unlink fails."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        target = tmp_path / "stuck.txt"
        target.write_text("data")
        tx.created_files.append(target)

        with (
            patch.object(Path, "unlink", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            tx.rollback()

        assert "failed to remove file" in caplog.text

    def test_rollback_logs_on_rmdir_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Rollback logs warning when rmdir fails."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        target = tmp_path / "stuck_dir"
        target.mkdir()
        tx.created_dirs.append(target)

        with (
            patch.object(Path, "rmdir", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            tx.rollback()

        assert "failed to remove dir" in caplog.text
