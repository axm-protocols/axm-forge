"""Unit tests for file_header hook (pure, no I/O)."""

from __future__ import annotations

from axm_ast.hooks.file_header import FileHeaderHook


class TestFileHeaderMissingPath:
    """Invalid path handling."""

    def test_file_header_missing_path(self) -> None:
        """Invalid path returns HookResult.fail with clear message."""
        hook = FileHeaderHook()
        result = hook.execute({}, files="foo.py", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


class TestEntryPointDiscoverable:
    """Entry point registration test."""

    def test_entry_point_discoverable(self) -> None:
        """'ast:file-header' is registered in axm.hooks entry points."""
        from importlib.metadata import entry_points

        hooks = entry_points(group="axm.hooks")
        names = [ep.name for ep in hooks]
        assert "ast:file-header" in names
