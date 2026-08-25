"""Integration: ``doc_impact`` undocumented detection honours ``doc_policy``.

Reproduces the four false-positive cases observed in the L4 lesson — a
docstringed private helper, an already-documented class, a docstringed check
function, and an untouched private symbol — and asserts none is reported as
undocumented, while a genuine public docstring-less gap still is. This pins the
seam between the ``doc_impact`` detector and the shared
``is_documentation_required`` policy end to end over a real temp package.
"""

from __future__ import annotations

from pathlib import Path

from axm_ast.core.cache import get_package
from axm_ast.core.doc_impact import analyze_doc_impact
from axm_ast.doc_policy import is_documentation_required
from axm_ast.models.nodes import ClassInfo, FunctionInfo

# One module holding every L4 case plus one true positive.
_SRC = (
    '"""Module."""\n'
    "\n"
    "\n"
    "def _helper() -> int:\n"
    '    """Docstringed private helper (L4 case 1)."""\n'
    "    return 1\n"
    "\n"
    "\n"
    "class AlreadyDocumented:\n"
    '    """Already-documented class (L4 case 2)."""\n'
    "\n"
    "\n"
    "def check_thing() -> bool:\n"
    '    """Docstringed check function (L4 case 3)."""\n'
    "    return True\n"
    "\n"
    "\n"
    "def _untouched() -> int:\n"
    "    return 2\n"  # untouched private symbol, no docstring (L4 case 4)
    "\n"
    "\n"
    "def real_gap() -> int:\n"
    "    return 3\n"  # public, no docstring → the genuine gap (true positive)
)

_L4_SYMBOLS = ["_helper", "AlreadyDocumented", "check_thing", "_untouched"]
_TRUE_POSITIVE = "real_gap"


def _make_pkg(tmp_path: Path) -> Path:
    """Write a minimal src-layout package containing every case, no prose docs."""
    pkg = tmp_path / "src" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""mypkg."""\n')
    (pkg / "core.py").write_text(_SRC)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0.1.0"\n'
    )
    return tmp_path


def test_l4_cases_not_flagged_true_positive_kept(tmp_path: Path) -> None:
    """The four L4 false positives vanish; the real public gap remains flagged.

    Asserts the end-to-end detector verdict (``analyze_doc_impact``) and, on the
    same real parsed nodes the detector consumes (via ``get_package``), that the
    shared ``is_documentation_required`` policy driving it agrees case by case —
    so the docstring/privacy signal comes from tree-sitter, not a hand-built
    node.
    """
    root = _make_pkg(tmp_path)
    symbols = [*_L4_SYMBOLS, _TRUE_POSITIVE]

    result = analyze_doc_impact(root, symbols)
    undocumented = set(result["undocumented"])

    # None of the four L4 cases may be reported …
    for sym in _L4_SYMBOLS:
        assert sym not in undocumented, f"{sym} should not be undocumented"
    # … while the genuine public docstring-less symbol is still caught.
    assert _TRUE_POSITIVE in undocumented

    # Read-only: schema unchanged, only the undocumented set shrank.
    assert set(result) == {"doc_refs", "undocumented", "stale_signatures"}

    # The predicate driving the detector judges the real parsed nodes the same.
    pkg = get_package(root)
    by_name: dict[str, FunctionInfo | ClassInfo] = {
        fn.name: fn for mod in pkg.modules for fn in mod.functions
    }
    by_name.update({cls.name: cls for mod in pkg.modules for cls in mod.classes})
    for sym in _L4_SYMBOLS:
        assert is_documentation_required(by_name[sym]) is False
    assert is_documentation_required(by_name[_TRUE_POSITIVE]) is True
