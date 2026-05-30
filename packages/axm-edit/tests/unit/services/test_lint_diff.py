"""Unit tests for compute_lint_diffs (pure function, no I/O)."""

from __future__ import annotations

import pytest

from axm_edit.services.lint_diff import compute_lint_diffs


class TestTaggedDiffFormat:
    """AC2: diff format is tagged_plus_minus with @L<n> hunks."""

    def test_tagged_diff_simple_replacement(self) -> None:
        post_agent = {"a.py": "x=1\ny=2\n"}
        post_lint = {"a.py": "x=1\ny=3\n"}
        rules = {"a.py": ["F841"]}

        result = compute_lint_diffs(post_agent, post_lint, rules)

        assert len(result) == 1
        assert result[0]["file"] == "a.py"
        assert result[0]["diff"] == "@L2\n-y=2\n+y=3"

    def test_multiple_hunks_ordered_by_line(self) -> None:
        pre_lines = [f"line{i}" for i in range(10)]
        post_lines = list(pre_lines)
        post_lines[1] = "mut1"
        post_lines[5] = "mut5"
        post_lines[8] = "mut8"
        post_agent = {"a.py": "\n".join(pre_lines) + "\n"}
        post_lint = {"a.py": "\n".join(post_lines) + "\n"}
        rules = {"a.py": ["F841"]}

        result = compute_lint_diffs(post_agent, post_lint, rules)

        diff = str(result[0]["diff"])
        assert "@L2" in diff
        assert "@L6" in diff
        assert "@L9" in diff
        # Ordered ascending
        assert diff.index("@L2") < diff.index("@L6") < diff.index("@L9")

    @pytest.mark.parametrize(
        ("post_agent", "post_lint", "expect"),
        [
            pytest.param(
                {"a.py": "keep\ndrop\nkeep2\n"},
                {"a.py": "keep\nkeep2\n"},
                ("-drop", "+", "+drop"),
                id="deletion_only_hunk",
            ),
            pytest.param(
                {"a.py": "a\nc\n"},
                {"a.py": "a\nb\nc\n"},
                ("+b", "-", "-b"),
                id="insertion_only_hunk",
            ),
        ],
    )
    def test_single_sign_hunk(
        self,
        post_agent: dict[str, str],
        post_lint: dict[str, str],
        expect: tuple[str, str, str],
    ) -> None:
        present, absent_sign, absent_token = expect
        result = compute_lint_diffs(post_agent, post_lint, {"a.py": ["F401"]})

        diff = str(result[0]["diff"])
        assert present in diff
        opposite_lines = [ln for ln in diff.splitlines() if ln.startswith(absent_sign)]
        assert absent_token not in opposite_lines


class TestRulesHandling:
    """AC3: rules deduplicated and sorted."""

    def test_rules_deduplicated_and_sorted(self) -> None:
        post_agent = {"a.py": "x=1\n"}
        post_lint = {"a.py": "x=2\n"}
        rules = {"a.py": ["I001", "F841", "I001"]}

        result = compute_lint_diffs(post_agent, post_lint, rules)

        assert result[0]["rules"] == ["F841", "I001"]

    def test_file_missing_from_rules_map_uses_empty_list(self) -> None:
        post_agent = {"a.py": "x=1\n"}
        post_lint = {"a.py": "x=2\n"}
        rules: dict[str, list[str]] = {}

        result = compute_lint_diffs(post_agent, post_lint, rules)

        assert len(result) == 1
        assert result[0]["rules"] == []
        assert "diff" in result[0]


class TestNoMutationReturnsEmpty:
    """AC5: no mutation -> empty list."""

    def test_no_mutation_returns_empty_list(self) -> None:
        post_agent = {"a.py": "x=1\n"}
        post_lint = {"a.py": "x=1\n"}
        rules = {"a.py": ["F841"]}

        result = compute_lint_diffs(post_agent, post_lint, rules)

        assert result == []


class TestFallback:
    """AC4: fallback when diff exceeds thresholds."""

    def test_fallback_when_diff_ratio_exceeds_threshold(self) -> None:
        pre_lines = [f"orig{i}" for i in range(10)]
        post_lines = list(pre_lines)
        for i in range(8):
            post_lines[i] = f"mutated{i}"
        post_agent = {"a.py": "\n".join(pre_lines) + "\n"}
        post_lint = {"a.py": "\n".join(post_lines) + "\n"}
        rules = {"a.py": ["F841"]}

        result = compute_lint_diffs(post_agent, post_lint, rules, max_ratio=0.5)

        assert len(result) == 1
        assert result[0].get("diff_skipped") == "file_reread_recommended"
        assert "diff" not in result[0]

    def test_fallback_when_diff_exceeds_4000_chars(self) -> None:
        # Big file where diff would exceed 4000 chars but ratio stays low
        pre_lines = [f"line_number_{i:04d}_original_content" for i in range(500)]
        post_lines = list(pre_lines)
        for i in range(150):
            post_lines[i] = f"mutated_line_{i:04d}_replacement_text_long"
        post_agent = {"a.py": "\n".join(pre_lines) + "\n"}
        post_lint = {"a.py": "\n".join(post_lines) + "\n"}
        rules = {"a.py": ["F841"]}

        result = compute_lint_diffs(
            post_agent, post_lint, rules, max_ratio=1.0, max_chars=4000
        )

        assert len(result) == 1
        assert result[0].get("diff_skipped") == "file_reread_recommended"
        assert "diff" not in result[0]
