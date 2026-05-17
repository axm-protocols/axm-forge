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
