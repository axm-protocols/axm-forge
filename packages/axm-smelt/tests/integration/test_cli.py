"""Integration tests for the smelt CLI (real I/O)."""

from __future__ import annotations

from pathlib import Path

from axm_smelt.cli import read_input


class TestCliIntegration:
    def test_read_input_valid_file(self, tmp_path: Path) -> None:
        """read_input reads content from an existing file."""
        p = tmp_path / "sample.txt"
        p.write_text("content here")
        assert read_input(p) == "content here"

    def test_cli_roundtrip_utf8_non_ascii(self, tmp_path: Path) -> None:
        """AC3: a non-ASCII utf-8 file round-trips unchanged through read_input."""
        content = "café naïve résumé 漢字 こんにちは"
        src = tmp_path / "input.txt"
        src.write_text(content, encoding="utf-8")
        assert read_input(src) == content
