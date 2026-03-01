"""Tests for Makefile adapter."""

from __future__ import annotations

from pathlib import Path


class TestMakefileDetection:
    """Tests for Makefile target detection."""

    def test_no_makefile_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty set when Makefile doesn't exist."""
        from axm_init.adapters.makefile import detect_makefile_targets

        targets = detect_makefile_targets(tmp_path)
        assert targets == set()

    def test_detect_targets_finds_lint_target(self, tmp_path: Path) -> None:
        """Detects 'lint' target in Makefile."""
        from axm_init.adapters.makefile import detect_makefile_targets

        makefile = tmp_path / "Makefile"
        makefile.write_text("lint:\n\tuv run ruff check .\n\ntest:\n\tuv run pytest\n")

        targets = detect_makefile_targets(tmp_path)
        assert "lint" in targets
        assert "test" in targets

    def test_detect_targets_finds_check_target(self, tmp_path: Path) -> None:
        """Detects 'check' target in Makefile."""
        from axm_init.adapters.makefile import detect_makefile_targets

        makefile = tmp_path / "Makefile"
        makefile.write_text("check: lint test\n\t@echo 'All checks passed'\n")

        targets = detect_makefile_targets(tmp_path)
        assert "check" in targets


class TestGetToolCommand:
    """Tests for tool command resolution."""

    def test_returns_make_target_when_available(self, tmp_path: Path) -> None:
        """Uses make target when Makefile has it."""
        from axm_init.adapters.makefile import get_tool_command

        makefile = tmp_path / "Makefile"
        makefile.write_text("lint:\n\tuv run ruff check .\n")

        cmd = get_tool_command(
            project_path=tmp_path,
            makefile_target="lint",
            fallback_cmd=["uv", "run", "ruff", "check", "."],
        )
        assert cmd == ["make", "lint"]

    def test_returns_fallback_when_no_makefile(self, tmp_path: Path) -> None:
        """Uses fallback command when no Makefile."""
        from axm_init.adapters.makefile import get_tool_command

        cmd = get_tool_command(
            project_path=tmp_path,
            makefile_target="lint",
            fallback_cmd=["uv", "run", "ruff", "check", "."],
        )
        assert cmd == ["uv", "run", "ruff", "check", "."]

    def test_returns_fallback_when_target_missing(self, tmp_path: Path) -> None:
        """Uses fallback when target not in Makefile."""
        from axm_init.adapters.makefile import get_tool_command

        makefile = tmp_path / "Makefile"
        makefile.write_text("build:\n\tpython -m build\n")

        cmd = get_tool_command(
            project_path=tmp_path,
            makefile_target="lint",
            fallback_cmd=["uv", "run", "ruff", "check", "."],
        )
        assert cmd == ["uv", "run", "ruff", "check", "."]
