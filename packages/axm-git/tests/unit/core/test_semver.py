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

    def test_patch_docs_chore(self) -> None:
        result = compute_bump(
            ["abc docs: readme", "def chore: cleanup"],
            "v0.7.0",
        )
        assert result.bump == "patch"
        assert result.next == "v0.7.1"

    def test_minor_feat(self) -> None:
        result = compute_bump(["abc feat: new api"], "v0.7.0")
        assert result.bump == "minor"
        assert result.next == "v0.8.0"

    def test_minor_breaking_pre1(self) -> None:
        """Pre-1.0: breaking change = minor bump (not major)."""
        result = compute_bump(["abc feat!: breaking"], "v0.7.0")
        assert result.bump == "minor"
        assert result.next == "v0.8.0"
        assert result.breaking

    def test_major_breaking_post1(self) -> None:
        """Post-1.0: breaking change = major bump."""
        result = compute_bump(["abc feat!: breaking"], "v1.0.0")
        assert result.bump == "major"
        assert result.next == "v2.0.0"
        assert result.breaking

    def test_breaking_change_in_body(self) -> None:
        result = compute_bump(["abc BREAKING CHANGE: removed api"], "v1.0.0")
        assert result.bump == "major"
        assert result.breaking

    def test_no_tags_defaults(self) -> None:
        """When no tag exists, v0.0.0 base → first feat gives v0.1.0."""
        result = compute_bump(["abc feat: initial"], "v0.0.0")
        assert result.bump == "minor"
        assert result.next == "v0.1.0"

    def test_scoped_feat(self) -> None:
        result = compute_bump(["abc feat(cli): add flag"], "v0.5.0")
        assert result.bump == "minor"
        assert result.next == "v0.6.0"

    def test_scoped_breaking(self) -> None:
        result = compute_bump(["abc fix(core)!: rename"], "v0.5.0")
        assert result.bump == "minor"
        assert result.next == "v0.6.0"
        assert result.breaking

    def test_minor_feat_post1(self) -> None:
        """Post-1.0: feat = minor bump."""
        result = compute_bump(["abc feat: new api"], "v1.2.0")
        assert result.bump == "minor"
        assert result.next == "v1.3.0"

    def test_returns_version_bump(self) -> None:
        result = compute_bump(["abc fix: x"], "v1.0.0")
        assert isinstance(result, VersionBump)
        assert result.current == "v1.0.0"
        assert result.commits == ["abc fix: x"]
