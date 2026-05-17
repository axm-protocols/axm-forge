"""Unit tests for semver computation."""

from __future__ import annotations

import pytest

from axm_git.core.semver import VersionBump, compute_bump, parse_tag


class TestParseTag:
    """Test parse_tag function."""

    def test_valid_with_prefix(self) -> None:
        assert parse_tag("v1.2.3") == (1, 2, 3)

    def test_valid_without_prefix(self) -> None:
        assert parse_tag("1.2.3") == (1, 2, 3)

    def test_zero_version(self) -> None:
        assert parse_tag("v0.0.0") == (0, 0, 0)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid semver"):
            parse_tag("not-a-version")


class TestComputeBump:
    """Test compute_bump version logic."""

    def test_patch_fix_only(self) -> None:
        result = compute_bump(["abc fix: bug"], "v0.7.0")
        assert result.bump == "patch"
        assert result.next == "v0.7.1"
        assert not result.breaking

    def test_breaking_change_in_body(self) -> None:
        result = compute_bump(["abc BREAKING CHANGE: removed api"], "v1.0.0")
        assert result.bump == "major"
        assert result.breaking

    @pytest.mark.parametrize(
        (
            "commits",
            "previous_tag",
            "expected_bump",
            "expected_next",
            "expected_breaking",
        ),
        [
            pytest.param(
                ["abc docs: readme", "def chore: cleanup"],
                "v0.7.0",
                "patch",
                "v0.7.1",
                False,
                id="patch_docs_chore",
            ),
            pytest.param(
                ["abc feat: new api"],
                "v0.7.0",
                "minor",
                "v0.8.0",
                False,
                id="minor_feat",
            ),
            pytest.param(
                ["abc feat: initial"],
                "v0.0.0",
                "minor",
                "v0.1.0",
                False,
                id="no_tags_defaults",
            ),
            pytest.param(
                ["abc feat(cli): add flag"],
                "v0.5.0",
                "minor",
                "v0.6.0",
                False,
                id="scoped_feat",
            ),
            pytest.param(
                ["abc feat: new api"],
                "v1.2.0",
                "minor",
                "v1.3.0",
                False,
                id="minor_feat_post1",
            ),
            pytest.param(
                ["abc feat!: breaking"],
                "v0.7.0",
                "minor",
                "v0.8.0",
                True,
                id="minor_breaking_pre1",
            ),
            pytest.param(
                ["abc feat!: breaking"],
                "v1.0.0",
                "major",
                "v2.0.0",
                True,
                id="major_breaking_post1",
            ),
            pytest.param(
                ["abc fix(core)!: rename"],
                "v0.5.0",
                "minor",
                "v0.6.0",
                True,
                id="scoped_breaking",
            ),
        ],
    )
    def test_bump_matrix(
        self,
        commits: list[str],
        previous_tag: str,
        expected_bump: str,
        expected_next: str,
        expected_breaking: bool,
    ) -> None:
        result = compute_bump(commits, previous_tag)
        assert result.bump == expected_bump
        assert result.next == expected_next
        assert result.breaking is expected_breaking

    def test_returns_version_bump(self) -> None:
        result = compute_bump(["abc fix: x"], "v1.0.0")
        assert isinstance(result, VersionBump)
        assert result.current == "v1.0.0"
        assert result.commits == ["abc fix: x"]
