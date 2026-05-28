"""Integration tests for axm_audit.core.fix.paths — real-filesystem helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.paths import module_path_for_test_file

pytestmark = pytest.mark.integration


def test_module_path_dotted_and_outside(tmp_path: Path) -> None:
    """AC2: module_path_for_test_file returns dotted path or None outside project."""
    project = tmp_path / "p"
    test_file = project / "tests" / "integration" / "test_foo.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("")
    assert module_path_for_test_file(test_file, project) == "tests.integration.test_foo"

    outside = tmp_path / "elsewhere" / "test_foo.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("")
    assert module_path_for_test_file(outside, project) is None


def test_module_path_returns_none_when_outside_tests_dir(tmp_path: Path) -> None:
    """AC2: module_path_for_test_file returns None for in-project non-tests paths."""
    project = tmp_path / "p"
    src_file = project / "src" / "axm_audit" / "mod.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("")
    assert module_path_for_test_file(src_file, project) is None
