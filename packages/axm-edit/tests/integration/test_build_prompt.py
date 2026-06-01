"""Split from ``test_lint_prompt_strategy.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.services.lint import build_prompt
from tests.integration._helpers import _make_errors, _write_lines

# ---------------------------------------------------------------------------
# Unit tests — prompt dispatch
# ---------------------------------------------------------------------------


class TestSmallFileGetsFullContent:
    """File at or under the 300-line threshold -> prompt contains the full file."""

    @pytest.mark.parametrize(
        ("num_lines", "filename", "expected"),
        [
            pytest.param(
                20,
                "small.py",
                ["1: line_0", "20: line_19", "15: line_14"],
                id="small_20_lines",
            ),
            pytest.param(
                300,
                "boundary.py",
                ["1: line_0", "300: line_299"],
                id="boundary_300_lines",
            ),
        ],
    )
    def test_full_content_in_prompt(
        self,
        tmp_path: Path,
        num_lines: int,
        filename: str,
        expected: list[str],
    ) -> None:
        lines = [f"line_{i} = {i}" for i in range(num_lines)]
        file_path = tmp_path / filename
        _write_lines(file_path, lines)

        errors = _make_errors(filename, ["E722"], line=15)
        prompt = build_prompt(file_path, errors)

        for marker in expected:
            assert marker in prompt, f"Prompt should contain {marker!r}"


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
        prompt = build_prompt(file_path, errors)

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
        prompt = build_prompt(file_path, errors)

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


class TestFileNoImportsErrorLine1:
    """File with no imports, error on line 1 of a script -> full file sent."""

    def test_no_imports_full_file(self, tmp_path: Path) -> None:
        lines = [f"print({i})" for i in range(20)]
        file_path = tmp_path / "script.py"
        _write_lines(file_path, lines)

        errors = _make_errors("script.py", ["E722"], line=1)
        prompt = build_prompt(file_path, errors)

        assert "1: print(0)" in prompt
        assert "20: print(19)" in prompt
