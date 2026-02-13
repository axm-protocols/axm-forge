"""Tests for edge cases in models, adapters, and makefile."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestProjectConfigValidation:
    """Cover models/project.py validation edges."""

    def test_empty_name_raises(self) -> None:
        """Empty name raises ValidationError."""
        from pydantic import ValidationError

        from axm_init.models.project import ProjectConfig

        with pytest.raises(ValidationError):
            ProjectConfig(name="")

    def test_whitespace_only_name_raises(self) -> None:
        """Whitespace-only name raises ValueError."""
        from axm_init.models.project import ProjectConfig

        with pytest.raises(ValueError, match="cannot be empty"):
            ProjectConfig(name="   ")

    def test_name_with_spaces_is_normalized(self) -> None:
        """Spaces in name are replaced with hyphens."""
        from axm_init.models.project import ProjectConfig

        config = ProjectConfig(name="  My Cool Project  ")
        assert config.name == "my-cool-project"


class TestPyPIAdapterError:
    """Cover adapters/pypi.py error paths."""

    def test_empty_name_returns_error(self) -> None:
        """Empty package name returns ERROR status."""
        from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

        adapter = PyPIAdapter()
        assert adapter.check_availability("") == AvailabilityStatus.ERROR

    @patch("axm_init.adapters.pypi.httpx.get")
    def test_unexpected_status_returns_error(self, mock_get: MagicMock) -> None:
        """Non-200/404 status code returns ERROR."""
        from axm_init.adapters.pypi import AvailabilityStatus, PyPIAdapter

        mock_get.return_value.status_code = 500
        adapter = PyPIAdapter()
        assert adapter.check_availability("test") == AvailabilityStatus.ERROR


class TestMakefileEdgeCases:
    """Cover adapters/makefile.py line 22-23."""

    def test_unreadable_makefile(self, tmp_path: Path) -> None:
        """Makefile with read error returns empty set."""
        from axm_init.adapters.makefile import detect_makefile_targets

        makefile = tmp_path / "Makefile"
        makefile.write_bytes(b"\x80\x81\x82")  # Binary content

        # Should not raise, returns empty or parsed set
        result = detect_makefile_targets(tmp_path)
        assert isinstance(result, set)


class TestFilesystemTransactionRollback:
    """Cover filesystem.py rollback paths."""

    def test_rollback_removes_files(self, tmp_path: Path) -> None:
        """Rollback removes created files."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        test_file = tmp_path / "test.txt"
        tx.write_file(test_file, "hello")
        assert test_file.exists()

        tx.rollback()
        assert not test_file.exists()

    def test_rollback_noop_after_commit(self, tmp_path: Path) -> None:
        """Rollback does nothing after commit."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        test_file = tmp_path / "test.txt"
        tx.write_file(test_file, "hello")
        tx.commit()
        tx.rollback()
        assert test_file.exists()

    def test_transaction_context_manager_rollbacks_on_error(
        self, tmp_path: Path
    ) -> None:
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

    def test_rollback_removes_empty_dirs(self, tmp_path: Path) -> None:
        """Rollback removes empty directories."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        nested = tmp_path / "a" / "b" / "c"
        tx.create_dir(nested)
        assert nested.exists()

        tx.rollback()
        assert not nested.exists()
