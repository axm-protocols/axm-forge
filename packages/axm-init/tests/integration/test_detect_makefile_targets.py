"""Tests for Makefile adapter."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestMakefileDetection:
    """Tests for Makefile target detection."""

    def test_no_makefile_returns_empty(self, tmp_path: Path) -> None:
        """Returns empty set when Makefile doesn't exist."""
        from axm_init.adapters.makefile import detect_makefile_targets

        targets = detect_makefile_targets(tmp_path)
        assert targets == set()

    @pytest.mark.parametrize(
        ("makefile_body", "expected"),
        [
            pytest.param(
                "lint:\n\tuv run ruff check .\n\ntest:\n\tuv run pytest\n",
                {"lint", "test"},
                id="lint_and_test",
            ),
            pytest.param(
                "check: lint test\n\t@echo 'All checks passed'\n",
                {"check"},
                id="check_target",
            ),
        ],
    )
    def test_detect_targets_finds(
        self, tmp_path: Path, makefile_body: str, expected: set[str]
    ) -> None:
        """detect_makefile_targets surfaces declared targets."""
        from axm_init.adapters.makefile import detect_makefile_targets

        (tmp_path / "Makefile").write_text(makefile_body)
        assert expected <= detect_makefile_targets(tmp_path)


# ── Edge cases ───────────────────────────────────────────────────────────────


class TestMakefileEdgeCases:
    """Cover adapters/makefile.py line 22-23."""

    def test_unreadable_makefile(self, tmp_path: Path) -> None:
        """Makefile with undecodable bytes returns an empty set, not raises."""
        from axm_init.adapters.makefile import detect_makefile_targets

        makefile = tmp_path / "Makefile"
        makefile.write_bytes(b"\x80\x81\x82")

        result = detect_makefile_targets(tmp_path)
        assert result == set()
