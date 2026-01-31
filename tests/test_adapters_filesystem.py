"""Tests for FileSystemAdapter — RED phase."""

from pathlib import Path


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
