"""Unit tests for FileHeaderHook — pure context-dict logic (no I/O)."""

from __future__ import annotations

from pathlib import Path

from axm_ast.hooks.file_header import FileHeaderHook


class TestFileHeaderNoSourceBody:
    """No source_body or missing files key — skip gracefully."""

    def test_missing_files_key_skips(self, tmp_path: Path) -> None:
        """source_body with symbols but no files key returns skip."""
        context: dict[str, object] = {
            "source_body": {"symbols": "class Foo:\n    pass\n"},
        }
        hook = FileHeaderHook()
        result = hook.execute(context, path=str(tmp_path))

        assert result.success
        assert result.metadata["headers"] == []

    def test_empty_files_list_skips(self, tmp_path: Path) -> None:
        """source_body with empty files list returns skip."""
        context: dict[str, object] = {
            "source_body": {"files": []},
        }
        hook = FileHeaderHook()
        result = hook.execute(context, path=str(tmp_path))

        assert result.success
        assert result.metadata["headers"] == []
