"""Split from ``test_type_refs_impact_scoring.py``."""

from pathlib import Path

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.impact import find_type_refs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SELF_PKG = Path(__file__).resolve().parent.parent.parent / "src" / "axm_ast"


class TestTypeRefsDogfood:
    """Run type ref analysis on axm-ast itself."""

    def test_type_refs_dogfood(self) -> None:
        """PackageInfo is widely used in params/returns across axm-ast."""
        pkg = analyze_package(SELF_PKG)
        refs = find_type_refs(pkg, "PackageInfo")
        assert len(refs) >= 1, f"Expected ≥1 type refs to PackageInfo, got {len(refs)}"
        # Should include both param and return refs.
        ref_types = {r["ref_type"] for r in refs}
        assert "param" in ref_types
