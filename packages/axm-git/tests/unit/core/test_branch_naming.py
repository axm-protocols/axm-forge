"""Tests for branch naming convention utilities."""

from __future__ import annotations

import pytest

from axm_git.core.branch_naming import branch_name_from_ticket, slugify


class TestSlugify:
    """Tests for slugify."""

    def test_basic_slugify(self) -> None:
        """Lowercases and replaces non-alphanum with hyphens."""
        assert slugify("Add batch mode") == "add-batch-mode"

    def test_sanitization(self) -> None:
        """Removes special characters, keeps only a-z0-9 and hyphens."""
        result = slugify("Hello World! (v2.0) — special")
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in result)

    def test_max_length(self) -> None:
        """Slug is truncated to max_len characters."""
        title = "a " * 50  # 100 chars worth
        result = slugify(title, max_len=40)
        assert len(result) <= 40

    def test_truncation_at_word_boundary(self) -> None:
        """Truncation avoids cutting in the middle of a word."""
        title = "implement the very important feature for users"
        result = slugify(title, max_len=30)
        assert len(result) <= 30
        assert not result.endswith("-")

    def test_consecutive_hyphens_collapsed(self) -> None:
        """Multiple consecutive hyphens are collapsed to one."""
        result = slugify("foo  --  bar")
        assert "--" not in result
        assert "foo-bar" in result

    def test_no_trailing_hyphen(self) -> None:
        """Trailing hyphens are stripped."""
        result = slugify("hello-")
        assert not result.endswith("-")

    @pytest.mark.parametrize(
        "title",
        [
            pytest.param("", id="empty_string"),
            pytest.param("!!!", id="only_special_chars"),
        ],
    )
    def test_falls_back_to_untitled(self, title: str) -> None:
        """Slugify returns the 'untitled' fallback when nothing slug-worthy remains."""
        result = slugify(title)
        assert result == "untitled"


class TestBranchNameFromTicket:
    """Tests for branch_name_from_ticket."""

    @pytest.mark.parametrize(
        ("ticket", "title", "labels", "expected"),
        [
            pytest.param(
                "AXM-42",
                "Add batch mode",
                ["feature"],
                "feat/AXM-42-add-batch-mode",
                id="basic_feature",
            ),
            pytest.param(
                "AXM-42",
                "Add batch mode for CLI",
                ["feature"],
                "feat/AXM-42-add-batch-mode-for-cli",
                id="ac1_full_example",
            ),
            pytest.param(
                "AXM-1",
                "",
                [],
                "feat/AXM-1-untitled",
                id="empty_title_fallback",
            ),
            pytest.param(
                "AXM-7",
                "Fix: login (v2)!",
                ["bug"],
                "fix/AXM-7-fix-login-v2",
                id="special_chars_sanitized",
            ),
        ],
    )
    def test_full_branch_name_format(
        self,
        ticket: str,
        title: str,
        labels: list[str],
        expected: str,
    ) -> None:
        """Branch name combines type prefix, ticket ID, and sanitized slug."""
        result = branch_name_from_ticket(ticket, title, labels)
        assert result == expected

    @pytest.mark.parametrize(
        ("ticket", "title", "labels", "expected_prefix"),
        [
            pytest.param("AXM-10", "Fix login", ["bug"], "fix/", id="bug_label__fix"),
            pytest.param(
                "AXM-5",
                "Clean up utils",
                ["refactor"],
                "refactor/",
                id="refactor_label__refactor",
            ),
            pytest.param(
                "AXM-5",
                "Update readme",
                ["documentation"],
                "docs/",
                id="documentation_label__docs",
            ),
            pytest.param(
                "AXM-5",
                "Add unit tests",
                ["test"],
                "test/",
                id="test_label__test",
            ),
            pytest.param(
                "AXM-5",
                "Improve speed",
                ["enhancement"],
                "feat/",
                id="enhancement_label__feat",
            ),
            pytest.param(
                "AXM-5",
                "Bump deps",
                ["unknown-label"],
                "chore/",
                id="unknown_label__chore",
            ),
            pytest.param("AXM-5", "New thing", [], "feat/", id="no_labels__feat"),
            pytest.param(
                "AXM-5",
                "Mixed",
                ["feature", "bug"],
                "feat/",
                id="multiple_labels_first_wins__feat",
            ),
            pytest.param(
                "AXM-689",
                "refactor(market): reduce cyclomatic complexity",
                ["axm-market"],
                "refactor/",
                id="title_prefix_refactor_fallback",
            ),
            pytest.param(
                "AXM-100",
                "feat(market): add X",
                ["axm-market"],
                "feat/",
                id="title_prefix_feat_fallback",
            ),
            pytest.param(
                "AXM-101",
                "fix(market): broken Y",
                ["axm-market"],
                "fix/",
                id="title_prefix_fix_fallback",
            ),
            pytest.param(
                "AXM-102",
                "bump deps",
                ["axm-market"],
                "chore/",
                id="no_title_prefix__chore",
            ),
            pytest.param(
                "AXM-103",
                "refactor(x): something",
                ["bug"],
                "fix/",
                id="label_priority_over_title_prefix",
            ),
        ],
    )
    def test_commit_type_resolution(
        self,
        ticket: str,
        title: str,
        labels: list[str],
        expected_prefix: str,
    ) -> None:
        """Branch type prefix is resolved from labels first, then title prefix.

        Falls back to chore/.
        """
        result = branch_name_from_ticket(ticket, title, labels)
        assert result.startswith(expected_prefix)

    def test_very_long_title_truncated(self) -> None:
        """Slug part is truncated to 40 chars max."""
        long_title = "implement the very important and critical feature " * 5
        result = branch_name_from_ticket("AXM-99", long_title, ["feature"])
        # Extract slug part (after "feat/AXM-99-")
        slug = result.split("-", 2)[2] if result.count("-") >= 2 else ""
        assert len(slug) <= 40
