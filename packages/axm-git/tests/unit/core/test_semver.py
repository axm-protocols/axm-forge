"""Unit tests for semver computation."""

from __future__ import annotations

import pytest

from axm_git.core.semver import (
    VersionBump,
    classify_commit,
    compute_bump,
    parse_tag,
)


class TestClassifyCommit:
    """Test classify_commit faithful per-commit type labelling."""

    def test_classify_commit_returns_real_type_for_docs_chore(self) -> None:
        """AC1: non-feat/fix conventional types are returned verbatim."""
        assert classify_commit("docs(x): y") == ("docs", False)
        assert classify_commit("chore: z") == ("chore", False)
        assert classify_commit("refactor(a): b") == ("refactor", False)

    def test_classify_commit_keeps_feat_fix_and_breaking(self) -> None:
        """AC1: feat/fix keep their type; breaking flag is preserved."""
        assert classify_commit("feat: x") == ("feat", False)
        assert classify_commit("fix(a): y") == ("fix", False)
        assert classify_commit("feat!: z") == ("feat", True)

    def test_classify_commit_other_when_no_prefix(self) -> None:
        """AC1: a subject with no conventional prefix falls back to 'other'."""
        assert classify_commit("wip messy commit") == ("other", False)


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
                ["abc fix: bug"],
                "v0.7.0",
                "patch",
                "v0.7.1",
                False,
                id="prefixed_fix_only",
            ),
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
            pytest.param(
                ["feat: new api"],
                "v0.7.0",
                "minor",
                "v0.8.0",
                False,
                id="raw_minor_feat",
            ),
            pytest.param(
                ["feat(cli): add flag"],
                "v0.5.0",
                "minor",
                "v0.6.0",
                False,
                id="raw_scoped_feat",
            ),
            pytest.param(
                ["feat!: breaking"],
                "v1.0.0",
                "major",
                "v2.0.0",
                True,
                id="raw_major_breaking_post1",
            ),
            pytest.param(
                ["fix: bug"],
                "v0.7.0",
                "patch",
                "v0.7.1",
                False,
                id="raw_patch_fix",
            ),
            pytest.param(
                ["docs: readme", "chore: cleanup"],
                "v0.7.0",
                "patch",
                "v0.7.1",
                False,
                id="raw_patch_docs_chore",
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

    @pytest.mark.parametrize(
        ("current_tag", "expected_bump", "expected_next"),
        [
            pytest.param("v0.3.0", "minor", "v0.4.0", id="pre1_mixed"),
            pytest.param("v1.2.0", "minor", "v1.3.0", id="post1_mixed"),
        ],
    )
    def test_compute_bump_unchanged_for_mixed_commits(
        self, current_tag: str, expected_bump: str, expected_next: str
    ) -> None:
        """AC2: bump logic is invariant for a mixed feat/fix/docs/chore set."""
        commits = [
            "abc feat: new api",
            "bcd fix: bug",
            "cde docs: readme",
            "def chore: cleanup",
        ]
        result = compute_bump(commits, current_tag)
        assert result.bump == expected_bump
        assert result.next == expected_next

    def test_compute_bump_breaking_only_still_pinned(self) -> None:
        """AC2: a feat!:-only set keeps the documented pre/post-1.0 bumps."""
        assert compute_bump(["abc feat!: drop x"], "v0.3.0").next == "v0.4.0"
        assert compute_bump(["abc feat!: drop x"], "v1.2.0").next == "v2.0.0"

    @pytest.mark.parametrize(
        "commits",
        [
            pytest.param(["feat!: drop y"], id="raw_bang"),
            pytest.param(["BREAKING CHANGE: z"], id="raw_breaking_change"),
            pytest.param(
                ["abc BREAKING CHANGE: removed api"],
                id="prefixed_breaking_in_body",
            ),
        ],
    )
    def test_raw_breaking_is_major(self, commits: list[str]) -> None:
        """AC3: raw or prefixed breaking change classifies as major post-1.0."""
        result = compute_bump(commits, "v1.0.0")
        assert result.bump == "major"
        assert result.breaking
