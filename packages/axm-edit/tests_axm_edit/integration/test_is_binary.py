"""Split from ``test_utils.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.utils import is_binary


class TestIsBinaryUnit:
    """Unit tests for is_binary() across byte-content scenarios."""

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            pytest.param(b"hello\x00world", True, id="null_bytes"),
            pytest.param(
                bytes(range(0x01, 0x20)) * 100, True, id="high_nonprintable_ratio"
            ),
            pytest.param(b"Hello, world!\nLine 2\n", False, id="text_ascii"),
            pytest.param("Héllo café naïve".encode(), False, id="text_utf8_accents"),
            pytest.param(b"", False, id="empty_file"),
            pytest.param(None, False, id="nonexistent_file"),
            pytest.param(
                b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 10, True, id="png_header"
            ),
            pytest.param(
                b"A" * 70 + bytes([0x01]) * 30,
                False,
                id="exactly_30_percent_nonprintable",
            ),
            pytest.param(
                b"col1\tcol2\tcol3\n" * 100, False, id="text_with_tabs_newlines"
            ),
            pytest.param(b"A\x01B", True, id="very_short_file_with_nonprintable"),
        ],
    )
    def test_is_binary(
        self, tmp_path: Path, content: bytes | None, expected: bool
    ) -> None:
        f = tmp_path / "sample"
        if content is not None:
            f.write_bytes(content)
        assert is_binary(f) is expected
