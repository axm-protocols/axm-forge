"""Integration tests for backfill_missing_imports + invalidate_import_index."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.fix.cst_rewrite import (
    backfill_missing_imports,
    invalidate_import_index,
)

pytestmark = pytest.mark.integration


def test_backfill_missing_imports_falls_back_to_project_index(
    tmp_path: Path,
) -> None:
    tests_unit = tmp_path / "tests" / "unit"
    tests_unit.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests_unit / "__init__.py").write_text("")
    donor = tests_unit / "test_donor.py"
    donor.write_text("from pkg import shared_helper\n\n\ndef test_x():\n    pass\n")
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    shared_helper()\n")
    invalidate_import_index(tmp_path)
    msgs = backfill_missing_imports(source, target, project_path=tmp_path)
    assert "from pkg import shared_helper" in target.read_text()
    assert any("backfilled import for `shared_helper`" in m for m in msgs)


def test_backfill_missing_imports_synthesizes_from_helpers(tmp_path: Path) -> None:
    """A name defined only in ``tests/<tier>/_helpers.py`` is synthesised."""
    tests_unit = tmp_path / "tests" / "unit"
    tests_unit.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests_unit / "__init__.py").write_text("")
    (tests_unit / "_helpers.py").write_text("def make_widget():\n    return 1\n")
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    make_widget()\n")
    invalidate_import_index(tmp_path)
    msgs = backfill_missing_imports(source, target, project_path=tmp_path)
    assert "import make_widget" in target.read_text()
    assert any("backfilled import for `make_widget`" in m for m in msgs)


def test_backfill_missing_imports_synthesizes_helper_assignment(
    tmp_path: Path,
) -> None:
    """A module-level ``NAME = ...`` in ``_helpers.py`` is recognised.

    The helper assignment is synthesised.
    """
    tests_unit = tmp_path / "tests" / "unit"
    tests_unit.mkdir(parents=True)
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tests_unit / "__init__.py").write_text("")
    (tests_unit / "_helpers.py").write_text("SHARED_CONST = 42\n")
    source = tmp_path / "source.py"
    source.write_text("def test_a():\n    pass\n")
    target = tmp_path / "target.py"
    target.write_text("def test_b():\n    assert SHARED_CONST\n")
    invalidate_import_index(tmp_path)
    backfill_missing_imports(source, target, project_path=tmp_path)
    text = target.read_text()
    # The synthesised import is a top-level statement, before the test body and
    # never sunk into a TYPE_CHECKING guard (assignments are runtime imports).
    assert "if TYPE_CHECKING:" not in text
    assert text.index("import SHARED_CONST") < text.index("def test_b")


def test_backfill_missing_imports_malformed_target_is_noop(tmp_path: Path) -> None:
    """A target that fails to ast-parse yields no backfill and no crash."""
    source = tmp_path / "source.py"
    source.write_text("from pkg import helper\n")
    target = tmp_path / "target.py"
    original = "def test_b(:\n    helper()\n"
    target.write_text(original)
    assert backfill_missing_imports(source, target, project_path=tmp_path) == []
    assert target.read_text() == original
