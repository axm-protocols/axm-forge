"""Unit tests for ruff diagnostic filtering (pure function, no I/O)."""

from __future__ import annotations

from axm_edit.services.lint import filter_ruff_lines


class TestFilterRuffLines:
    """filter_ruff_lines keeps diagnostics and drops ruff summary noise."""

    def test_keeps_diagnostic_lines(self) -> None:
        stdout = "app.py:1:1: F401 unused import\napp.py:2:1: E722 bare except\n"
        assert filter_ruff_lines(stdout) == [
            "app.py:1:1: F401 unused import",
            "app.py:2:1: E722 bare except",
        ]

    def test_drops_summary_noise(self) -> None:
        stdout = (
            "app.py:1:1: F401 unused import\n"
            "Found 1 error.\n"
            "[*] 1 fixable with the `--fix` option.\n"
            "No fixes available.\n"
        )
        assert filter_ruff_lines(stdout) == ["app.py:1:1: F401 unused import"]

    def test_drops_blank_lines(self) -> None:
        stdout = "\napp.py:1:1: F401 unused\n\n   \n"
        assert filter_ruff_lines(stdout) == ["app.py:1:1: F401 unused"]

    def test_empty_input_returns_empty(self) -> None:
        assert filter_ruff_lines("") == []
