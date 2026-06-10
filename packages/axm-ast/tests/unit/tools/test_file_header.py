"""Unit tests for AstFileHeaderTool (real filesystem I/O via tmp_path)."""

from __future__ import annotations

from pathlib import Path

from axm_ast.tools.file_header import AstFileHeaderTool


class TestAstFileHeaderTool:
    """Test AstFileHeaderTool behavior."""

    def test_name(self) -> None:
        """Tool registers under the ast_file_header name."""
        assert AstFileHeaderTool().name == "ast_file_header"

    def test_extract_success(self, tmp_path: Path) -> None:
        """A real file yields its header content in the data payload."""
        (tmp_path / "mod.py").write_text(
            '"""Module docstring."""\n\nimport os\n\n__all__ = ["thing"]\n'
        )
        result = AstFileHeaderTool().execute(files=["mod.py"], path=str(tmp_path))
        assert result.success
        headers = result.data["headers"]
        assert len(headers) == 1
        assert headers[0]["file"] == "mod.py"
        assert "import os" in headers[0]["header"]
        assert '__all__ = ["thing"]' in headers[0]["header"]

    def test_max_lines_respected(self, tmp_path: Path) -> None:
        """Only the first ``max_lines`` lines are kept per file."""
        body = "".join(f"line{i}\n" for i in range(50))
        (tmp_path / "big.py").write_text(body)
        result = AstFileHeaderTool().execute(
            files=["big.py"], path=str(tmp_path), max_lines=5
        )
        assert result.success
        header = result.data["headers"][0]["header"]
        assert header.splitlines() == ["line0", "line1", "line2", "line3", "line4"]

    def test_missing_file_skipped(self, tmp_path: Path) -> None:
        """A missing file is skipped, not an error, leaving headers empty."""
        result = AstFileHeaderTool().execute(
            files=["does_not_exist.py"], path=str(tmp_path)
        )
        assert result.success
        assert result.data["headers"] == []

    def test_path_not_a_directory(self, tmp_path: Path) -> None:
        """A path that is not a directory returns failure."""
        file_path = tmp_path / "not_a_dir.py"
        file_path.write_text("x = 1\n")
        result = AstFileHeaderTool().execute(files=["whatever.py"], path=str(file_path))
        assert not result.success
        assert "not a directory" in (result.error or "")

    def test_duplicate_files_deduplicated(self, tmp_path: Path) -> None:
        """The same file listed twice yields a single header entry."""
        (tmp_path / "mod.py").write_text('"""Doc."""\nimport sys\n')
        result = AstFileHeaderTool().execute(
            files=["mod.py", "mod.py"], path=str(tmp_path)
        )
        assert result.success
        assert len(result.data["headers"]) == 1
