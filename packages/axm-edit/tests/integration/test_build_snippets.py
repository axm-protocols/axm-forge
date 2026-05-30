"""Split from ``test_lint_prompt_strategy.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.services.lint import build_snippets

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_errors(file: str, codes: list[str], *, line: int = 1) -> list[str]:
    """Build ruff-style error strings."""
    return [f"{file}:{line}:{1}: {code} Some error description" for code in codes]


def _write_lines(path: Path, lines: list[str]) -> None:
    """Write lines to a file with trailing newline."""
    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestAllErrorsInHeader:
    """Errors on lines 1-5 of a 400-line file -> header covers errors, no duplicates."""

    def test_no_duplicate_ranges(self, tmp_path: Path) -> None:
        lines = [f"import mod_{i}" for i in range(10)]
        lines.append("class Foo:")
        lines.extend([f"    x_{i} = {i}" for i in range(389)])
        assert len(lines) == 400

        file_path = tmp_path / "large.py"
        _write_lines(file_path, lines)

        errors = [
            *_make_errors("large.py", ["E401"], line=1),
            *_make_errors("large.py", ["E401"], line=3),
            *_make_errors("large.py", ["E401"], line=5),
        ]
        snippets = build_snippets(file_path, errors)

        # Header lines should appear exactly once (no duplicates)
        assert snippets.count("1: import mod_0") == 1, "Line 1 should appear once"
        # Distant lines should not be present
        assert "200:" not in snippets


class TestOverlappingHeaderAndSnippet:
    """Error on line 12, header ends line 10 -> ranges merge correctly."""

    def test_ranges_merge(self, tmp_path: Path) -> None:
        lines = [f"import mod_{i}" for i in range(10)]  # lines 1-10: header
        lines.append("class Bar:")  # line 11: header ends at 10
        lines.extend([f"    y_{i} = {i}" for i in range(389)])
        assert len(lines) == 400

        file_path = tmp_path / "overlap.py"
        _write_lines(file_path, lines)

        errors = _make_errors("overlap.py", ["E722"], line=12)
        snippets = build_snippets(file_path, errors)

        # Header (lines 1-10) and snippet around line 12 should merge seamlessly
        assert "1: import mod_0" in snippets, "Header start should be present"
        assert "12:" in snippets, "Error line should be present"
        # No gap marker between header and snippet (they overlap)
        # Lines 1 through ~17 should be one continuous block
        assert "10: import mod_9" in snippets, "Header end should be present"
