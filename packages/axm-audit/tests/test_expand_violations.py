from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.hooks.quality_check import _expand_violations


@pytest.fixture()
def project_path(tmp_path: Path) -> Path:
    return tmp_path


# --- Edge case: no failed items ---


def test_no_failed_items_returns_empty_list(project_path: Path) -> None:
    """When there are no failed items, violations list is empty."""
    result = _expand_violations(project_path, [])
    assert result == []


# --- Items with inner errors (type checks) ---


def test_expands_inner_errors(project_path: Path) -> None:
    """Items with details.errors get expanded per entry."""
    failed_items = [
        {
            "rule_id": "type-check",
            "details": {
                "errors": [
                    {"file": "a.py", "line": 10, "message": "err1", "code": "E1"},
                    {"file": "b.py", "line": 20, "message": "err2", "code": "E2"},
                ],
            },
        },
    ]
    with patch("axm_audit.hooks.quality_check._read_snippet", return_value="snippet"):
        result = _expand_violations(project_path, failed_items)

    assert len(result) == 2
    assert result[0]["file"] == "a.py"
    assert result[0]["line"] == 10
    assert result[0]["message"] == "err1"
    assert result[0]["code"] == "E1"
    assert result[0]["rule_id"] == "type-check"
    assert result[0]["snippet"] == "snippet"
    assert result[1]["file"] == "b.py"
    assert result[1]["line"] == 20


# --- Items with inner issues (lint checks) ---


def test_expands_inner_issues(project_path: Path) -> None:
    """Items with details.issues get expanded per entry."""
    failed_items = [
        {
            "rule_id": "lint-check",
            "details": {
                "issues": [
                    {"file": "c.py", "line": 5, "message": "iss1", "code": "W1"},
                ],
            },
        },
    ]
    with patch("axm_audit.hooks.quality_check._read_snippet", return_value="ctx"):
        result = _expand_violations(project_path, failed_items)

    assert len(result) == 1
    assert result[0]["file"] == "c.py"
    assert result[0]["line"] == 5
    assert result[0]["message"] == "iss1"
    assert result[0]["code"] == "W1"
    assert result[0]["rule_id"] == "lint-check"
    assert result[0]["snippet"] == "ctx"


# --- Fallback: item without inner errors/issues ---


def test_fallback_violation_without_inner_list(project_path: Path) -> None:
    """Items without inner errors/issues produce a single fallback violation."""
    failed_items = [
        {
            "rule_id": "complexity",
            "message": "too complex",
            "details": {},
        },
    ]
    result = _expand_violations(project_path, failed_items)

    assert len(result) == 1
    assert result[0]["file"] == ""
    assert result[0]["line"] == 0
    assert result[0]["message"] == "too complex"
    assert result[0]["code"] == "complexity"
    assert result[0]["rule_id"] == "complexity"
    assert result[0]["snippet"] is None


def test_fallback_violation_no_details_key(project_path: Path) -> None:
    """Items with no details key at all produce a fallback violation."""
    failed_items = [
        {
            "rule_id": "security",
            "message": "unsafe",
        },
    ]
    result = _expand_violations(project_path, failed_items)

    assert len(result) == 1
    assert result[0]["rule_id"] == "security"
    assert result[0]["message"] == "unsafe"
    assert result[0]["snippet"] is None


# --- Mixed items ---


def test_mixed_items_expanded_and_fallback(project_path: Path) -> None:
    """Mix of items with and without inner lists."""
    failed_items = [
        {
            "rule_id": "lint",
            "details": {
                "issues": [
                    {"file": "x.py", "line": 1, "message": "m1", "code": "C1"},
                    {"file": "y.py", "line": 2, "message": "m2", "code": "C2"},
                ],
            },
        },
        {
            "rule_id": "complexity",
            "message": "high cc",
            "details": {},
        },
    ]
    with patch("axm_audit.hooks.quality_check._read_snippet", return_value=None):
        result = _expand_violations(project_path, failed_items)

    assert len(result) == 3
    assert result[0]["rule_id"] == "lint"
    assert result[1]["rule_id"] == "lint"
    assert result[2]["rule_id"] == "complexity"
    assert result[2]["snippet"] is None


# --- Snippet integration ---


def test_snippet_called_with_correct_args(project_path: Path) -> None:
    """_read_snippet receives project_path, file, and line from entry."""
    failed_items = [
        {
            "rule_id": "r1",
            "details": {
                "errors": [
                    {"file": "f.py", "line": 42, "message": "m", "code": "c"},
                ],
            },
        },
    ]
    with patch(
        "axm_audit.hooks.quality_check._read_snippet", return_value="snip"
    ) as mock_snippet:
        _expand_violations(project_path, failed_items)

    mock_snippet.assert_called_once_with(project_path, "f.py", 42)


# --- Sparse entries ---


def test_entry_missing_fields_use_defaults(project_path: Path) -> None:
    """Inner entries with missing fields get safe defaults."""
    failed_items = [
        {
            "rule_id": "r1",
            "details": {
                "errors": [
                    {},
                ],
            },
        },
    ]
    with patch("axm_audit.hooks.quality_check._read_snippet", return_value=None):
        result = _expand_violations(project_path, failed_items)

    assert len(result) == 1
    assert result[0]["file"] == ""
    assert result[0]["line"] == 0
    assert result[0]["message"] == ""
    assert result[0]["code"] == ""
    assert result[0]["rule_id"] == "r1"
    assert result[0]["snippet"] is None
