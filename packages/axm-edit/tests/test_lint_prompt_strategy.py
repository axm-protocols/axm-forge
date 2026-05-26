"""Tests for prompt strategy: full-file vs header+snippets based on file size."""

from __future__ import annotations

from pathlib import Path

from axm_edit.services.lint import (
    _build_prompt,
    _build_snippets,
    _find_header_end,
)

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
# Unit tests — _find_header_end
# ---------------------------------------------------------------------------


class TestHeaderDetectionClass:
    """File with `class Foo:` on line 15 -> _find_header_end returns 14."""

    def test_finds_class_boundary(self, tmp_path: Path) -> None:
        lines = [f"import mod_{i}" for i in range(14)]  # lines 1-14
        lines.append("class Foo:")  # line 15 (0-indexed 14)
        lines.extend([f"    attr_{i} = {i}" for i in range(10)])  # body
        _write_lines(tmp_path / "mod.py", lines)

        all_lines = (tmp_path / "mod.py").read_text().splitlines()
        result = _find_header_end(all_lines)
        assert result == 14, f"Expected 14, got {result}"


class TestHeaderDetectionNoClass:
    """File with no class/def (script) -> _find_header_end returns total lines."""

    def test_script_file_returns_total(self, tmp_path: Path) -> None:
        lines = [f"x_{i} = {i}" for i in range(20)]  # pure script, no class/def
        _write_lines(tmp_path / "script.py", lines)

        all_lines = (tmp_path / "script.py").read_text().splitlines()
        result = _find_header_end(all_lines)
        assert result == len(all_lines), (
            f"Expected {len(all_lines)} (whole file), got {result}"
        )


# ---------------------------------------------------------------------------
# Unit tests — prompt dispatch
# ---------------------------------------------------------------------------


class TestSmallFileGetsFullContent:
    """20-line .py file, error on line 15 -> prompt contains line 1 through 20."""

    def test_full_content_in_prompt(self, tmp_path: Path) -> None:
        lines = [f"line_{i} = {i}" for i in range(20)]
        file_path = tmp_path / "small.py"
        _write_lines(file_path, lines)

        errors = _make_errors("small.py", ["E722"], line=15)
        prompt = _build_prompt(file_path, errors)

        # Prompt should contain first and last lines
        assert "1: line_0" in prompt, "Prompt should contain first line"
        assert "20: line_19" in prompt, "Prompt should contain last line"
        # Should contain the error line
        assert "15: line_14" in prompt, "Prompt should contain error line"


class TestLargeFileGetsHeaderPlusSnippets:
    """400-line .py file (imports on 1-10, error on line 350) ->
    prompt contains lines 1-10 AND 345-355, NOT line 200."""

    def test_header_and_snippets_in_prompt(self, tmp_path: Path) -> None:
        lines = [f"import mod_{i}" for i in range(10)]  # lines 1-10: imports
        lines.append("class App:")  # line 11: class definition
        lines.extend([f"    x_{i} = {i}" for i in range(389)])  # pad to 400 lines
        assert len(lines) == 400

        file_path = tmp_path / "large.py"
        _write_lines(file_path, lines)

        errors = _make_errors("large.py", ["E722"], line=350)
        prompt = _build_prompt(file_path, errors)

        # Header lines (imports) should be present
        assert "1: import mod_0" in prompt, "Prompt should contain header (line 1)"
        assert "10: import mod_9" in prompt, "Prompt should contain header (line 10)"
        # Snippet around error should be present
        assert "350:" in prompt, "Prompt should contain error line 350"
        # Distant unrelated lines should NOT be present
        assert "200:" not in prompt, "Prompt should NOT contain distant line 200"


# ---------------------------------------------------------------------------
# Existing test contract update
# ---------------------------------------------------------------------------


class TestExistingSnippetTestPasses:
    """Existing 50-line file fixture: 50 < 300 so full file is sent."""

    def test_small_file_gets_full_prompt(self, tmp_path: Path) -> None:
        lines = [f"line_{i} = {i}" for i in range(50)]
        lines[2] = "try:\n    x = 1\nexcept:\n    pass"
        file_path = tmp_path / "app.py"
        _write_lines(file_path, lines)

        errors = _make_errors("app.py", ["E722"], line=3)
        prompt = _build_prompt(file_path, errors)

        # 50 lines < 300: full file should be sent
        # Nearby lines still present
        assert "line_1" in prompt, "Prompt should contain nearby context"
        # Distant lines now also present (full file mode)
        assert "line_40" in prompt, (
            "50-line file should use full-file prompt (< 300 threshold)"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFileExactly300Lines:
    """Boundary: file exactly 300 lines -> uses full-file prompt (≤ 300)."""

    def test_boundary_uses_full_file(self, tmp_path: Path) -> None:
        lines = [f"x_{i} = {i}" for i in range(300)]
        file_path = tmp_path / "boundary.py"
        _write_lines(file_path, lines)

        errors = _make_errors("boundary.py", ["E722"], line=150)
        prompt = _build_prompt(file_path, errors)

        # Should contain first and last lines (full file)
        assert "1: x_0" in prompt, "Boundary file should use full-file prompt"
        assert "300: x_299" in prompt, "Boundary file should contain last line"


class TestFileNoImportsErrorLine1:
    """File with no imports, error on line 1 of a script -> full file sent."""

    def test_no_imports_full_file(self, tmp_path: Path) -> None:
        lines = [f"print({i})" for i in range(20)]
        file_path = tmp_path / "script.py"
        _write_lines(file_path, lines)

        errors = _make_errors("script.py", ["E722"], line=1)
        prompt = _build_prompt(file_path, errors)

        assert "1: print(0)" in prompt
        assert "20: print(19)" in prompt


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
        snippets = _build_snippets(file_path, errors)

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
        snippets = _build_snippets(file_path, errors)

        # Header (lines 1-10) and snippet around line 12 should merge seamlessly
        assert "1: import mod_0" in snippets, "Header start should be present"
        assert "12:" in snippets, "Error line should be present"
        # No gap marker between header and snippet (they overlap)
        # Lines 1 through ~17 should be one continuous block
        assert "10: import mod_9" in snippets, "Header end should be present"
