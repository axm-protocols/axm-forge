"""Transactional filesystem writes roll back atomically on failure."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest


class TestRollbackBehavior:
    """Rollback handles files, directories, and partial-failure logging."""

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

    def test_rollback_removes_empty_dirs(self, tmp_path: Path) -> None:
        """Rollback removes empty directories."""
        from axm_init.adapters.filesystem import Transaction

        tx = Transaction()
        nested = tmp_path / "a" / "b" / "c"
        tx.create_dir(nested)
        assert nested.exists()

        tx.rollback()
        assert not nested.exists()

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
