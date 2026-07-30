"""Integration tests for the smelt CLI (real I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_smelt.cli import read_input


class TestCliIntegration:
    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("content here", id="ascii_file"),
            pytest.param("café naïve résumé 漢字 こんにちは", id="utf8_non_ascii"),
        ],
    )
    def test_read_input_roundtrip(self, tmp_path: Path, content: str) -> None:
        """read_input reads file content unchanged (AC3: utf-8 round-trips)."""
        src = tmp_path / "input.txt"
        src.write_text(content, encoding="utf-8")
        assert read_input(src) == content
