"""Unit mirror of :mod:`axm_edit.tools.file_bytes` (pure ``render_text``).

No I/O: the report is built in memory and only the compact rendering is
exercised.
"""

from __future__ import annotations

from axm_edit.tools.file_bytes import render_text

SHA256 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def _report() -> dict[str, object]:
    """Return an in-memory file-bytes report payload."""
    return {
        "path": "/tmp/sample.txt",
        "size": 12,
        "sha256": SHA256,
        "encoding": "utf-8",
        "encoding_ok": True,
        "verdict": "literal_where_escaped_expected",
        "literal_non_ascii_count": 2,
        "literal_non_ascii": [],
        "escaped_sequence_count": 0,
        "escaped_sequences": [],
        "mismatch": None,
        "hint": "doubler le backslash avant de passer par MCP",
    }


def test_render_text_exposes_verdict_and_sha256() -> None:
    """AC9: the compact rendering carries the verdict word and the sha256."""
    rendered = render_text(_report())

    assert isinstance(rendered, str)
    assert "verdict" in rendered.lower()
    assert SHA256 in rendered


def test_render_text_reports_size_and_bounded_counters() -> None:
    """AC9: the rendering also shows the size and the bounded counters."""
    rendered = render_text(_report())

    assert "12" in rendered
    assert "2" in rendered
