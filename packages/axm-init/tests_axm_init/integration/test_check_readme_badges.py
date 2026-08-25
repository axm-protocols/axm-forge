"""Tests for checks.docs — documentation checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.docs import (
    check_readme_badges,
)


class TestCheckReadmeBadges:
    """Tests for check_readme_badges (AC4)."""

    def test_badges_present(self, tmp_path: Path) -> None:
        """README with both axm-audit and axm-init badges passes."""
        (tmp_path / "README.md").write_text(
            "# My Project\n"
            "![axm-audit](https://img.shields.io/endpoint?url=...axm-audit.json)\n"
            "![axm-init](https://img.shields.io/endpoint?url=...axm-init.json)\n"
        )
        r = check_readme_badges(tmp_path)
        assert r.passed is True
        assert r.weight == 2

    def test_badges_missing(self, tmp_path: Path) -> None:
        """README without badge strings fails."""
        (tmp_path / "README.md").write_text("# My Project\n\nNo badges here.\n")
        r = check_readme_badges(tmp_path)
        assert r.passed is False
        assert "2 badge(s)" in r.message

    def test_partial_badges(self, tmp_path: Path) -> None:
        """README with only one badge fails."""
        (tmp_path / "README.md").write_text(
            "# My Project\n"
            "![axm-audit](https://img.shields.io/endpoint?url=...axm-audit.json)\n"
        )
        r = check_readme_badges(tmp_path)
        assert r.passed is False
        assert "1 badge(s)" in r.message
        assert "axm-init" in r.details[0]

    def test_no_readme(self, empty_project: Path) -> None:
        """No README.md fails."""
        r = check_readme_badges(empty_project)
        assert r.passed is False
        assert "not found" in r.message
