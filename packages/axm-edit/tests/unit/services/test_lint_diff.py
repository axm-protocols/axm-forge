"""Unit tests for compute_lint_diffs (pure function, no I/O)."""

from __future__ import annotations

import pytest

from axm_edit.services.lint_diff import (
    ImportRemoval,
    compute_lint_diffs,
    extract_import_removals,
)


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


class TestExtractImportRemovals:
    """AC1-3: isolate F401/F811 removals with import/symbol name + file + code."""

    def test_f401_removal_is_surfaced_with_name(self) -> None:
        diagnostics = ["pkg/mod.py:1:8: F401 [*] `os` imported but unused"]

        result = extract_import_removals(diagnostics)

        assert list(result) == ["pkg/mod.py"]
        (removal,) = result["pkg/mod.py"]
        assert removal == ImportRemoval(name="os", file="pkg/mod.py", code="F401")

    def test_f811_redefinition_is_surfaced_with_name(self) -> None:
        diagnostics = ["pkg/mod.py:5:1: F811 Redefinition of unused `os` from line 1"]

        result = extract_import_removals(diagnostics)

        (removal,) = result["pkg/mod.py"]
        assert removal.name == "os"
        assert removal.file == "pkg/mod.py"
        assert removal.code == "F811"

    def test_no_f401_or_f811_yields_empty(self) -> None:
        diagnostics = ["pkg/mod.py:10:89: E501 Line too long (95 > 88)"]

        assert extract_import_removals(diagnostics) == {}

    def test_other_codes_are_excluded(self) -> None:
        diagnostics = [
            "pkg/mod.py:10:89: E501 Line too long (95 > 88)",
            "pkg/mod.py:3:5: F841 Local variable `x` is assigned to but never used",
        ]

        assert extract_import_removals(diagnostics) == {}

    def test_path_resolver_is_applied_to_keys(self) -> None:
        diagnostics = ["/abs/pkg/mod.py:1:8: F401 [*] `os` imported but unused"]

        result = extract_import_removals(
            diagnostics, path_resolver=lambda p: p.rsplit("/", 1)[-1]
        )

        assert list(result) == ["mod.py"]
        assert result["mod.py"][0].name == "os"

    def test_mixed_codes_keep_only_dangerous_removals(self) -> None:
        diagnostics = [
            "a.py:1:8: F401 [*] `os` imported but unused",
            "a.py:2:1: E501 Line too long",
            "b.py:9:1: F811 Redefinition of unused `sys` from line 2",
        ]

        result = extract_import_removals(diagnostics)

        assert set(result) == {"a.py", "b.py"}
        assert [r.code for r in result["a.py"]] == ["F401"]
        assert [r.code for r in result["b.py"]] == ["F811"]


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
