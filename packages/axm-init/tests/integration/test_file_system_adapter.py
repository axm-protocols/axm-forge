"""Atomic file and directory write operations against a real filesystem."""

from __future__ import annotations

from pathlib import Path

import pytest


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

    @pytest.mark.parametrize(
        "relpath",
        [
            pytest.param(("newdir",), id="flat"),
            pytest.param(("a", "b", "c"), id="nested"),
        ],
    )
    def test_create_dir(self, tmp_path: Path, relpath: tuple[str, ...]) -> None:
        """create_dir creates flat and nested directories."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()
        target = tmp_path.joinpath(*relpath)

        result = adapter.create_dir(target)

        assert result is True
        assert target.is_dir()


class TestTransactionCommitsAndRollsBack:
    """Transactions keep files on success and remove them on failure."""

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

        assert not (tmp_path / "keep.txt").exists()

    def test_transaction_tracks_created_files(self, tmp_path: Path) -> None:
        """Transaction tracks files for rollback."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        adapter = FileSystemAdapter()

        with adapter.transaction() as tx:
            tx.write_file(tmp_path / "tracked.txt", "data")
            assert len(tx.created_files) == 1

    def test_context_manager_rollbacks_on_error(self, tmp_path: Path) -> None:
        """Transaction context manager rolls back on exception."""
        from axm_init.adapters.filesystem import FileSystemAdapter

        fs = FileSystemAdapter()
        test_file = tmp_path / "will_be_removed.txt"

        with pytest.raises(RuntimeError):
            with fs.transaction() as tx:
                tx.write_file(test_file, "temporary")
                assert test_file.exists()
                raise RuntimeError("boom")

        assert not test_file.exists()
