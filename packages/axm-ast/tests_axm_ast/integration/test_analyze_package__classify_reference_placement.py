"""Integration tests for classify_reference_placement over a real package.

Covers AC3: over a real package analysed from disk via analyze_package, the
classifier returns "top_level" for a symbol defined in that package and
"call_time" for an absent one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.analyzer import analyze_package


@pytest.mark.integration
def test_existing_vs_absent_symbol_classification(tmp_path: Path) -> None:
    """AC3: real analysed package separates an existing symbol from an absent one.

    classify_reference_placement is imported call-time (in-body) so the module
    collects cleanly and REDs inside the body until the helper lands.
    """
    from axm_ast.core.analyzer import classify_reference_placement

    pkg_dir = tmp_path / "sample_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "mod.py").write_text("def Baz() -> int:\n    return 1\n")

    pkg = analyze_package(pkg_dir)

    assert classify_reference_placement(pkg, "Baz") == "top_level"
    assert classify_reference_placement(pkg, "Nope") == "call_time"
