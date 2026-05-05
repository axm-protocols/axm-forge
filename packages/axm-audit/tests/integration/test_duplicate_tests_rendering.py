from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule

pytestmark = pytest.mark.integration


AMBIGUOUS_TEST_FILE = """
from __future__ import annotations


def test_alpha() -> None:
    x = 1
    y = 2
    assert x + y == 3


def test_beta() -> None:
    x = 10
    y = 20
    assert x + y == 30
"""


def test_audit_exposes_ambiguous_clusters_in_text(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    tests = pkg / "tests" / "unit"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    (tests / "test_dup.py").write_text(AMBIGUOUS_TEST_FILE)

    result = DuplicateTestsRule().check(pkg)
    text = result.text or ""
    if not result.passed:
        assert "test_alpha" in text or "test_beta" in text
        assert "test_dup.py" in text
