"""FileSystem Adapter — atomic filesystem operations with rollback.

Provides safe file/directory creation with transaction support for
atomic multi-file operations used during project scaffolding.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Transaction context for atomic filesystem operations.

    Tracks created files/directories for rollback on failure.
    """

    created_files: list[Path] = field(default_factory=list)
    created_dirs: list[Path] = field(default_factory=list)
    _committed: bool = False

    def write_file(self, path: Path, content: str) -> bool:
        """Write file and track for potential rollback."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        self.created_files.append(path)
        return True

    def create_dir(self, path: Path) -> bool:
        """Create directory and track for potential rollback."""
        path.mkdir(parents=True, exist_ok=True)
        self.created_dirs.append(path)
        return True

    def commit(self) -> None:
        """Mark transaction as committed (no rollback)."""
        self._committed = True

    def rollback(self) -> None:
        """Remove all created files and directories."""
        if self._committed:
            return

        # Remove files first
        for f in reversed(self.created_files):
            try:
                if f.exists():
                    f.unlink()
            except OSError as exc:
                logger.warning("Rollback: failed to remove file %s: %s", f, exc)

        # Remove directories (reverse order for nested)
        for d in reversed(self.created_dirs):
            try:
                if d.exists() and not any(d.iterdir()):
                    d.rmdir()
            except OSError as exc:
                logger.warning("Rollback: failed to remove dir %s: %s", d, exc)


class FileSystemAdapter:
    """Adapter for atomic filesystem operations.

    Supports both single operations and transactions for multi-file
    atomic operations with rollback on failure.
    """

    def write_file(self, path: Path, content: str) -> bool:
        """Write content to a file, creating parent directories.

        Args:
            path: Target file path.
            content: File content to write.

        Returns:
            True if successful.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return True

    def create_dir(self, path: Path) -> bool:
        """Create a directory (and parents).

        Args:
            path: Directory path to create.

        Returns:
            True if successful.
        """
        path.mkdir(parents=True, exist_ok=True)
        return True

    @contextmanager
    def transaction(self) -> Generator[Transaction, None, None]:
        """Context manager for atomic multi-file operations.

        On success: files are kept.
        On exception: all created files are rolled back.

        Yields:
            Transaction object for tracked operations.
        """
        tx = Transaction()
        try:
            yield tx
            tx.commit()
        except Exception:
            tx.rollback()
            raise
