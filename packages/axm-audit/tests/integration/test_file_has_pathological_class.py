"""Integration tests for axm_audit.core.fix.tests_ast — real-file pathology."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.tests_ast import file_has_pathological_class

pytestmark = pytest.mark.integration


def test_file_has_pathological_class_true_false(tmp_path: Path) -> None:
    """AC4: True iff file contains pathological class with divergent canonical."""
    benign = tmp_path / "test_benign.py"
    benign.write_text("class TestB:\n    def test_a(self): pass\n")
    assert file_has_pathological_class(benign) is False

    bad = tmp_path / "test_bad.py"
    bad.write_text(
        "class TestX:\n"
        "    def __init__(self): pass\n"
        "    def test_alpha_one(self): pass\n"
        "    def test_beta_two(self): pass\n"
    )
    assert file_has_pathological_class(bad) is True
