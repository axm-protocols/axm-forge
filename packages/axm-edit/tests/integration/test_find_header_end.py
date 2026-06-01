"""Split from ``test_lint_prompt_strategy.py``."""

from __future__ import annotations

from pathlib import Path

from axm_edit.services.lint import find_header_end
from tests.integration._helpers import _write_lines

# ---------------------------------------------------------------------------
# Unit tests — find_header_end
# ---------------------------------------------------------------------------


class TestHeaderDetectionClass:
    """File with `class Foo:` on line 15 -> find_header_end returns 14."""

    def test_finds_class_boundary(self, tmp_path: Path) -> None:
        lines = [f"import mod_{i}" for i in range(14)]  # lines 1-14
        lines.append("class Foo:")  # line 15 (0-indexed 14)
        lines.extend([f"    attr_{i} = {i}" for i in range(10)])  # body
        _write_lines(tmp_path / "mod.py", lines)

        all_lines = (tmp_path / "mod.py").read_text().splitlines()
        result = find_header_end(all_lines)
        assert result == 14, f"Expected 14, got {result}"


class TestHeaderDetectionNoClass:
    """File with no class/def (script) -> find_header_end returns total lines."""

    def test_script_file_returns_total(self, tmp_path: Path) -> None:
        lines = [f"x_{i} = {i}" for i in range(20)]  # pure script, no class/def
        _write_lines(tmp_path / "script.py", lines)

        all_lines = (tmp_path / "script.py").read_text().splitlines()
        result = find_header_end(all_lines)
        assert result == len(all_lines), (
            f"Expected {len(all_lines)} (whole file), got {result}"
        )
