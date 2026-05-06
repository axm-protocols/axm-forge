from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from axm_audit.core.rules.dependencies import (
    DependencyHygieneRule,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(code: str, module: str, message: str) -> dict[str, Any]:
    """Build a deptry-style issue dict."""
    return {"error": {"code": code, "message": message}, "module": module}


@pytest.fixture()
def rule() -> DependencyHygieneRule:
    return DependencyHygieneRule()


_PATCH_RUN = "axm_audit.core.rules.dependencies.run_deptry"
_PATCH_FILTER = "axm_audit.core.rules.dependencies._filter_false_positives"


# ---------------------------------------------------------------------------
# Functional tests
# ---------------------------------------------------------------------------


class TestIntegrationScope:
    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_deps_hygiene_top_issues(self, mock_deptry, _mock_filter, rule, tmp_path):
        mock_deptry.return_value = [_make_issue("DEP001", "foo", "missing")]
        result = rule._check_single(tmp_path)
        assert result.text == "• DEP001 foo: missing dep"
        assert len(result.details["top_issues"]) == 1
        assert result.details["top_issues"][0]["code"] == "DEP001"
        assert result.details["top_issues"][0]["module"] == "foo"

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_single_package_text_format(
        self, mock_deptry, _mock_filter, rule, tmp_path
    ):
        mock_deptry.return_value = [
            _make_issue("DEP002", "requests", "requests imported but not used"),
            _make_issue("DEP001", "foo", "foo imported but missing"),
        ]
        result = rule._check_single(tmp_path)
        assert result.text == "• DEP002 requests: unused dep\n• DEP001 foo: missing dep"

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_workspace_text_includes_member(
        self, mock_deptry, _mock_filter, rule, tmp_path
    ):
        member_a = tmp_path / "pkg-a"
        member_b = tmp_path / "pkg-b"
        member_a.mkdir()
        member_b.mkdir()

        def deptry_side_effect(path):
            if path == member_a:
                return [_make_issue("DEP001", "foo", "missing")]
            if path == member_b:
                return [_make_issue("DEP002", "bar", "unused")]
            return []

        mock_deptry.side_effect = deptry_side_effect
        result = rule._check_workspace(tmp_path, [member_a, member_b])
        lines = result.text.split("\n")
        assert len(lines) == 2
        assert lines[0].endswith("(pkg-a)")
        assert lines[1].endswith("(pkg-b)")

    # ---------------------------------------------------------------------------
    # Edge cases
    # ---------------------------------------------------------------------------

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_unknown_deptry_code(self, mock_deptry, _mock_filter, rule, tmp_path):
        mock_deptry.return_value = [_make_issue("DEP999", "mod", "some new rule")]
        result = rule._check_single(tmp_path)
        assert result.text == "• DEP999 mod: some new rule"

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_zero_issues_passed(self, mock_deptry, _mock_filter, rule, tmp_path):
        mock_deptry.return_value = []
        result = rule._check_single(tmp_path)
        assert result.text is None
        assert result.details["top_issues"] == []

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_five_issue_cap(self, mock_deptry, _mock_filter, rule, tmp_path):
        issues = [_make_issue("DEP001", f"mod{i}", "missing") for i in range(8)]
        mock_deptry.return_value = issues
        result = rule._check_single(tmp_path)
        lines = result.text.split("\n")
        assert len(lines) == 5
        assert len(result.details["top_issues"]) == 5

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_workspace_member_with_no_issues(
        self, mock_deptry, _mock_filter, rule, tmp_path
    ):
        member_a = tmp_path / "pkg-a"
        member_b = tmp_path / "pkg-b"
        member_c = tmp_path / "pkg-c"
        for m in (member_a, member_b, member_c):
            m.mkdir()

        def deptry_side_effect(path):
            if path == member_b:
                return [_make_issue("DEP001", "foo", "missing")]
            return []

        mock_deptry.side_effect = deptry_side_effect
        result = rule._check_workspace(tmp_path, [member_a, member_b, member_c])
        assert result.text is not None
        lines = result.text.split("\n")
        assert len(lines) == 1
        assert "(pkg-b)" in lines[0]

    @patch(_PATCH_FILTER, side_effect=lambda issues, _: issues)
    @patch(_PATCH_RUN)
    def test_empty_member_string_in_single_mode(
        self, mock_deptry, _mock_filter, rule, tmp_path
    ):
        mock_deptry.return_value = [_make_issue("DEP001", "foo", "missing")]
        result = rule._check_single(tmp_path)
        assert result.text is not None
        assert "(" not in result.text
