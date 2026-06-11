"""Unit tests for AstFileHeaderTool (no I/O — identity contract)."""

from __future__ import annotations

from axm_ast.tools.file_header import AstFileHeaderTool


class TestAstFileHeaderToolIdentity:
    """Test the tool's static identity contract."""

    def test_name(self) -> None:
        """Tool registers under the ast_file_header name."""
        assert AstFileHeaderTool().name == "ast_file_header"
