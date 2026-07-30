"""Integration tests for delete_source_if_empty_tests (real tmp_path I/O)."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import delete_source_if_empty_tests

pytestmark = pytest.mark.integration


def test_delete_source_if_empty_tests_unlinks_when_no_tests(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def helper():\n    return 1\n")
    delete_source_if_empty_tests(f)
    assert not f.exists()


def test_delete_source_if_empty_tests_keeps_file_with_tests(tmp_path: Path) -> None:
    f = tmp_path / "t.py"
    f.write_text("def test_real():\n    assert True\n")
    delete_source_if_empty_tests(f)
    assert f.exists()


def test_delete_source_if_empty_tests_missing_file_is_noop(tmp_path: Path) -> None:
    f = tmp_path / "absent.py"
    delete_source_if_empty_tests(f)
    assert not f.exists()
