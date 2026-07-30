"""Split from ``test_workspace_checks.py``."""

from pathlib import Path

import pytest

from axm_init.checks.workspace import check_members_consistent


class TestMembersConsistent:
    """Tests for check_members_consistent."""

    def test_valid(self, ws_root: Path) -> None:
        """Member with pyproject.toml + src/ + tests/ passes."""
        result = check_members_consistent(ws_root)
        assert result.passed
        assert result.weight == 2

    def test_missing_tests(self, ws_root: Path) -> None:
        """Member missing tests/ fails with detail."""
        # Remove tests dir
        import shutil

        member = ws_root / "packages" / "pkg-a" / "tests"
        shutil.rmtree(member)
        result = check_members_consistent(ws_root)
        assert not result.passed
        assert any("tests/" in d for d in result.details)

    def test_no_members_passes(self, tmp_path: Path) -> None:
        """No members is valid (workspace just configured)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        result = check_members_consistent(tmp_path)
        assert result.passed


class TestResolveMemberDirsEdge:
    """Cover member-dir resolution edge cases via public check_members_consistent.

    When member resolution yields an empty list, check_members_consistent
    returns passed=True with the "No members yet" message — exercising the
    same branches that previously imported _resolve_member_dirs directly.
    """

    @pytest.mark.parametrize(
        "pyproject_content",
        [
            pytest.param(None, id="no_pyproject"),
            pytest.param(
                '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = []\n',
                id="empty_members",
            ),
            pytest.param('[project]\nname = "ws"\n', id="no_workspace_section"),
        ],
    )
    def test_no_members_returns_empty(
        self, tmp_path: Path, pyproject_content: str | None
    ) -> None:
        """Empty/absent member resolution → check passes with 'No members yet'."""
        from axm_init.checks.workspace import check_members_consistent

        if pyproject_content is not None:
            (tmp_path / "pyproject.toml").write_text(pyproject_content)
        result = check_members_consistent(tmp_path)
        assert result.passed
        assert "No members yet" in result.message


class TestMembersConsistentMissing:
    """Cover lines 102, 104: missing pyproject.toml and src/."""

    def test_missing_pyproject_in_member(self, tmp_path: Path) -> None:
        """Member without pyproject.toml → flagged."""
        from axm_init.checks.workspace import check_members_consistent

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        # Create a pyproject.toml so glob matches, but then remove it
        # Actually, member dirs are resolved by glob + has pyproject check
        # So we need pyproject to exist for _resolve_member_dirs to include it
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        (member / "tests").mkdir()
        # No src/ directory
        result = check_members_consistent(tmp_path)
        assert not result.passed
        assert any("src/" in d for d in result.details)

    def test_missing_src_and_tests(self, tmp_path: Path) -> None:
        """Member missing both src/ and tests/ → both flagged."""
        from axm_init.checks.workspace import check_members_consistent

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )
        member = tmp_path / "packages" / "pkg-a"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n')
        # No src/ or tests/
        result = check_members_consistent(tmp_path)
        assert not result.passed
        details_text = " ".join(result.details)
        assert "src/" in details_text
        assert "tests/" in details_text
