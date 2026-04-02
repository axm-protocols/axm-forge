"""Tests for FileHeaderHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.hooks.file_header import FileHeaderHook

# ── Unit tests ─────────────────────────────────────────────────────


class TestFileHeaderSingleFile:
    """Single file header extraction."""

    def test_file_header_single_file(self, tmp_path: Path) -> None:
        """Returns first 30 lines of a 50-line file."""
        src = tmp_path / "example.py"
        lines = [f"line {i}\n" for i in range(1, 51)]
        src.write_text("".join(lines))

        hook = FileHeaderHook()
        result = hook.execute({}, files="example.py", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "example.py"
        assert "line 1" in headers[0]["header"]
        assert "line 30" in headers[0]["header"]
        assert "line 31" not in headers[0]["header"]

    def test_file_header_short_file(self, tmp_path: Path) -> None:
        """Returns all lines of a file shorter than 30 lines."""
        src = tmp_path / "short.py"
        lines = [f"line {i}\n" for i in range(1, 11)]
        src.write_text("".join(lines))

        hook = FileHeaderHook()
        result = hook.execute({}, files="short.py", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert "line 10" in headers[0]["header"]


class TestFileHeaderDedup:
    """Deduplication when multiple symbols reference the same file."""

    def test_file_header_dedup(self, tmp_path: Path) -> None:
        """Two references to the same file produce a single header entry."""
        src = tmp_path / "mod.py"
        src.write_text("import os\nclass Foo:\n    pass\nclass Bar:\n    pass\n")

        hook = FileHeaderHook()
        result = hook.execute({}, files="mod.py\nmod.py", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "mod.py"


class TestFileHeaderMissingFile:
    """Missing file handling — graceful skip."""

    def test_file_header_missing_file(self, tmp_path: Path) -> None:
        """Non-existent path is silently skipped."""
        hook = FileHeaderHook()
        result = hook.execute({}, files="nonexistent.py", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 0


class TestFileHeaderEmptyFile:
    """Empty file edge case."""

    def test_file_header_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns header as empty string."""
        src = tmp_path / "empty.py"
        src.write_text("")

        hook = FileHeaderHook()
        result = hook.execute({}, files="empty.py", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "empty.py"
        assert headers[0]["header"] == ""


class TestFileHeaderBinaryFile:
    """Binary file edge case."""

    def test_file_header_binary_file(self, tmp_path: Path) -> None:
        """Non-UTF-8 file is skipped with warning."""
        src = tmp_path / "binary.bin"
        src.write_bytes(b"\x80\x81\x82\xff\xfe")

        hook = FileHeaderHook()
        result = hook.execute({}, files="binary.bin", path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 0


class TestFileHeaderNoSourceBody:
    """No source_body or missing files key — skip gracefully."""

    def test_no_source_body(self, tmp_path: Path) -> None:
        """When no files param and no source_body in context, return empty."""
        hook = FileHeaderHook()
        result = hook.execute({}, path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 0

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


class TestFileHeaderFromSourceBody:
    """Extract files from source_body.files metadata."""

    def test_reads_files_from_metadata(self, tmp_path: Path) -> None:
        """Reads file list from source_body['files'] metadata key."""
        src = tmp_path / "src" / "a.py"
        src.parent.mkdir(parents=True)
        src.write_text("from __future__ import annotations\nimport logging\n")

        context: dict[str, object] = {
            "source_body": {
                "symbols": "class Foo:\n    pass\n",
                "files": ["src/a.py"],
            },
        }

        hook = FileHeaderHook()
        result = hook.execute(context, path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "src/a.py"


class TestFileHeaderMissingPath:
    """Invalid path handling."""

    def test_file_header_missing_path(self) -> None:
        """Invalid path returns HookResult.fail with clear message."""
        hook = FileHeaderHook()
        result = hook.execute({}, files="foo.py", path="/invalid/nonexistent")
        assert not result.success
        assert result.error is not None
        assert "not a directory" in result.error


# ── Functional tests ───────────────────────────────────────────────


class TestEntryPointDiscoverable:
    """Entry point registration test."""

    def test_entry_point_discoverable(self) -> None:
        """'ast:file-header' is registered in axm.hooks entry points."""
        from importlib.metadata import entry_points

        hooks = entry_points(group="axm.hooks")
        names = [ep.name for ep in hooks]
        assert "ast:file-header" in names


class TestHookOnRealPackage:
    """Integration test on axm-ast itself."""

    def test_hook_on_real_package(self) -> None:
        """Extract headers from axm-ast source files."""
        src_path = Path(__file__).resolve().parent.parent / "src" / "axm_ast"
        if not src_path.is_dir():
            pytest.skip("axm-ast source not found at expected path")

        hook = FileHeaderHook()
        result = hook.execute({}, files="hooks/source_body.py", path=str(src_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "hooks/source_body.py"
        assert "SourceBodyHook" in headers[0]["header"]
        assert "from __future__ import annotations" in headers[0]["header"]
