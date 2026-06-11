"""Unit tests for the AstFileHeaderTool dual-format text renderers."""

from __future__ import annotations

from axm_ast.tools.file_header_text import render_failure_text, render_text


class TestRenderText:
    """Test the success-path header renderer."""

    def test_header_line_reports_file_count(self) -> None:
        """The first line summarizes the number of rendered files."""
        text = render_text([{"file": "a.py", "header": "import os"}])
        assert text.splitlines()[0] == "ast_file_header | ✓ | 1 file(s)"

    def test_empty_headers_render_zero_count(self) -> None:
        """An empty header list still renders a well-formed summary line."""
        assert render_text([]) == "ast_file_header | ✓ | 0 file(s)"

    def test_each_file_block_has_name_and_header(self) -> None:
        """Each entry contributes a ``# <file>`` block followed by its header."""
        text = render_text(
            [
                {"file": "a.py", "header": "import os"},
                {"file": "b.py", "header": "import sys"},
            ]
        )
        assert "# a.py" in text
        assert "import os" in text
        assert "# b.py" in text
        assert "import sys" in text

    def test_header_trailing_whitespace_is_stripped(self) -> None:
        """A header's trailing whitespace is rstripped in the rendered block."""
        text = render_text([{"file": "a.py", "header": "import os\n\n"}])
        assert "import os\n\n" not in text
        assert text.rstrip().endswith("import os")

    def test_missing_keys_default_to_empty(self) -> None:
        """An entry without ``file``/``header`` keys renders empty placeholders."""
        text = render_text([{}])
        assert "ast_file_header | ✓ | 1 file(s)" in text


class TestRenderFailureText:
    """Test the failure-path renderer."""

    def test_failure_renders_error_message(self) -> None:
        """The failure line carries the error string after the ✗ marker."""
        assert render_failure_text(error="boom") == "ast_file_header | ✗ | boom"
