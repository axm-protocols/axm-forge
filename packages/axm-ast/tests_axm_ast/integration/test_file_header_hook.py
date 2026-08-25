"""Unit tests for FileHeaderHook — pure context-dict logic (no I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.hooks.file_header import FileHeaderHook


class TestFileHeaderNoSourceBody:
    """No source_body or missing files key — skip gracefully."""

    @pytest.mark.parametrize(
        "source_body",
        [
            pytest.param(
                {"symbols": "class Foo:\n    pass\n"},
                id="missing_files_key",
            ),
            pytest.param({"files": []}, id="empty_files_list"),
        ],
    )
    def test_source_body_without_usable_files_skips(
        self, tmp_path: Path, source_body: dict[str, object]
    ) -> None:
        """source_body lacking a non-empty files key returns skip."""
        context: dict[str, object] = {"source_body": source_body}
        hook = FileHeaderHook()
        result = hook.execute(context, path=str(tmp_path))

        assert result.success
        assert result.metadata["headers"] == []


class TestFileHeaderSingleFile:
    """Single file header extraction."""

    @pytest.mark.parametrize(
        ("filename", "num_lines", "present", "absent"),
        [
            pytest.param(
                "example.py",
                50,
                ["line 1", "line 30"],
                ["line 31"],
                id="long_file_truncated_at_30",
            ),
            pytest.param(
                "short.py",
                10,
                ["line 10"],
                [],
                id="short_file_all_lines",
            ),
        ],
    )
    def test_file_header_returns_first_30_lines(
        self,
        tmp_path: Path,
        filename: str,
        num_lines: int,
        present: list[str],
        absent: list[str],
    ) -> None:
        """Header holds the first 30 lines (all lines when file is shorter)."""
        src = tmp_path / filename
        src.write_text("".join(f"line {i}\n" for i in range(1, num_lines + 1)))

        hook = FileHeaderHook()
        result = hook.execute({}, files=filename, path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == filename
        for substr in present:
            assert substr in headers[0]["header"]
        for substr in absent:
            assert substr not in headers[0]["header"]


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


class TestFileHeaderNoSourceBodyFromFileHeaderIntegration:
    """No source_body or missing files key — skip gracefully."""

    def test_no_source_body(self, tmp_path: Path) -> None:
        """When no files param and no source_body in context, return empty."""
        hook = FileHeaderHook()
        result = hook.execute({}, path=str(tmp_path))

        assert result.success
        headers = result.metadata["headers"]
        assert len(headers) == 0


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
