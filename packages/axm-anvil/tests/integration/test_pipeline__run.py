"""Integration test: the axm-audit fix pipeline must not crash on a corpus
whose ``Test*`` classes each define a ``def test_basic`` method.

Covers AXM-1769 AC3/AC4: when SPLIT/FLATTEN-style reorganisation feeds a
symbol list to ``move_symbols``, a method name like ``test_basic`` must be
filtered to top-level source symbols and never reach anvil as a movable
name — the pipeline converges or fails cleanly, never ``SymbolNotFoundError``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from axm_audit.core.fix.pipeline import run

pytestmark = pytest.mark.integration


DUPLICATED_METHOD_CORPUS = (
    "import pytest\n\n\n"
    "class TestAlpha:\n"
    "    def test_basic(self) -> None:\n"
    "        assert 1 + 1 == 2\n\n"
    "    def test_alpha_extra(self) -> None:\n"
    '        assert "a" == "a"\n\n\n'
    "class TestBeta:\n"
    "    def test_basic(self) -> None:\n"
    "        assert 2 + 2 == 4\n\n"
    "    def test_beta_extra(self) -> None:\n"
    '        assert "b" == "b"\n'
)


def _make_corpus(root: Path) -> Path:
    test_dir = root / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_duplicated_methods.py"
    test_file.write_text(DUPLICATED_METHOD_CORPUS)
    return test_file


def test_apply_converges_on_duplicated_method_corpus(tmp_path: Path) -> None:
    """AC3, AC4: run(apply=True) raises no SymbolNotFoundError.

    Tree stays collectable.
    """
    test_file = _make_corpus(tmp_path)

    try:
        report = run(tmp_path, apply=True)
    except Exception as exc:
        assert "SymbolNotFoundError" not in type(exc).__name__, (
            f"pipeline crashed with a method-name move: {exc!r}"
        )
        raise

    # The corpus must remain a syntactically-valid, collectable tree.
    for produced in test_file.parent.rglob("test_*.py"):
        ast.parse(produced.read_text())

    # If a non-movable name was dropped, the cause must be visible.
    warnings = getattr(report, "warnings", [])
    assert isinstance(warnings, list)
