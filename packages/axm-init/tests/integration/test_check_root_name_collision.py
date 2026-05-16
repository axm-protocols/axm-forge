"""Tests for workspace-specific checks."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks.workspace import (
    check_root_name_collision,
)

# ── check_root_name_collision (AXM-313) ──────────────────────────────────────


class TestRootNameCollision:
    """Tests for check_root_name_collision."""

    def test_root_name_collision_detected(self, tmp_path: Path) -> None:
        """Root name == member name → fails."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "pkg-a"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        result = check_root_name_collision(tmp_path)
        assert not result.passed
        assert "collides" in result.message

    def test_root_name_collision_ok(self, ws_root: Path) -> None:
        """Root name differs from members → passes."""
        result = check_root_name_collision(ws_root)
        assert result.passed
        assert result.weight == 3

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_root_name_collision(tmp_path)
        assert result.passed
        assert "No members" in result.message

    def test_case_insensitive_collision(self, tmp_path: Path) -> None:
        """Case-insensitive collision detected."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "My-App"\n'
            '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "my-app"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "my-app"\n')
        result = check_root_name_collision(tmp_path)
        assert not result.passed


class TestRootNameCollisionNoToml:
    """Cover line 283: no pyproject.toml at root."""

    def test_no_pyproject_passes(self, tmp_path: Path) -> None:
        from axm_init.checks.workspace import check_root_name_collision

        result = check_root_name_collision(tmp_path)
        assert result.passed
        assert "No pyproject.toml" in result.message
