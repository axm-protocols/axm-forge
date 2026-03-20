"""Tests for branch naming convention utilities."""

from __future__ import annotations

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

    def test_empty_title(self) -> None:
        """Empty title returns fallback slug."""
        result = slugify("")
        assert result == "untitled"

    def test_special_chars_only(self) -> None:
        """Title with only special chars returns fallback slug."""
        result = slugify("!!!")
        assert result == "untitled"


class TestBranchNameFromTicket:
    """Tests for branch_name_from_ticket."""

    def test_basic_branch_name(self) -> None:
        """Returns formatted branch name with type, ticket ID, and slug."""
        result = branch_name_from_ticket("AXM-42", "Add batch mode", ["feature"])
        assert result == "feat/AXM-42-add-batch-mode"

    def test_full_example_from_ac(self) -> None:
        """AC1: matches the acceptance criteria example."""
        result = branch_name_from_ticket(
            "AXM-42", "Add batch mode for CLI", ["feature"]
        )
        assert result == "feat/AXM-42-add-batch-mode-for-cli"

    def test_fix_type_from_bug_label(self) -> None:
        """Bug label maps to fix/ prefix."""
        result = branch_name_from_ticket("AXM-10", "Fix login", ["bug"])
        assert result.startswith("fix/")

    def test_refactor_type(self) -> None:
        """Refactor label maps to refactor/ prefix."""
        result = branch_name_from_ticket("AXM-5", "Clean up utils", ["refactor"])
        assert result.startswith("refactor/")

    def test_docs_type(self) -> None:
        """Documentation label maps to docs/ prefix."""
        result = branch_name_from_ticket("AXM-5", "Update readme", ["documentation"])
        assert result.startswith("docs/")

    def test_test_type(self) -> None:
        """Test label maps to test/ prefix."""
        result = branch_name_from_ticket("AXM-5", "Add unit tests", ["test"])
        assert result.startswith("test/")

    def test_enhancement_maps_to_feat(self) -> None:
        """Enhancement label also maps to feat/ prefix."""
        result = branch_name_from_ticket("AXM-5", "Improve speed", ["enhancement"])
        assert result.startswith("feat/")

    def test_chore_type_as_default(self) -> None:
        """Unknown labels default to chore/ prefix."""
        result = branch_name_from_ticket("AXM-5", "Bump deps", ["unknown-label"])
        assert result.startswith("chore/")

    def test_no_labels_defaults_to_feat(self) -> None:
        """Empty labels list defaults to feat/ prefix."""
        result = branch_name_from_ticket("AXM-5", "New thing", [])
        assert result.startswith("feat/")

    def test_multiple_matching_labels_first_wins(self) -> None:
        """When multiple labels match, first match wins by priority order."""
        result = branch_name_from_ticket("AXM-5", "Mixed", ["feature", "bug"])
        assert result.startswith("feat/")

    def test_empty_title_fallback(self) -> None:
        """Empty title produces valid branch with fallback slug."""
        result = branch_name_from_ticket("AXM-1", "", [])
        assert result == "feat/AXM-1-untitled"

    def test_very_long_title_truncated(self) -> None:
        """Slug part is truncated to 40 chars max."""
        long_title = "implement the very important and critical feature " * 5
        result = branch_name_from_ticket("AXM-99", long_title, ["feature"])
        # Extract slug part (after "feat/AXM-99-")
        slug = result.split("-", 2)[2] if result.count("-") >= 2 else ""
        assert len(slug) <= 40

    def test_special_chars_in_title(self) -> None:
        """Special characters in title are sanitized."""
        result = branch_name_from_ticket("AXM-7", "Fix: login (v2)!", ["bug"])
        assert result == "fix/AXM-7-fix-login-v2"
