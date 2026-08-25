from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.coupling import classify_module_role

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Behavioral tests — exercise prefix detection / internal-import logic
# indirectly through the public ``classify_module_role`` surface.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module_name", "imports", "expected_role"),
    [
        pytest.param(
            "pkg.a.b",
            [],
            "leaf",
            id="empty_imports_returns_leaf",
        ),
        pytest.param(
            "pkg.a.b",
            ["os.path", "sys", "external.mod", "another.lib.util"],
            "leaf",
            id="all_external_imports_returns_leaf",
        ),
        pytest.param(
            "pkg.parent.current",
            ["pkg.parent.sib1", "pkg.parent.sib2", "pkg.parent.sib3"],
            "orchestrator",
            id="exactly_three_siblings_returns_orchestrator",
        ),
    ],
)
def test_classify_module_role(
    tmp_path: Path, module_name: str, imports: list[str], expected_role: str
) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").touch()

    result = classify_module_role(module_name, imports, tmp_path)

    assert result == expected_role


def _make_pkg(tmp_path: Path, pkg_name: str = "pkg") -> Path:
    """Create a minimal package under tmp_path/src for src_path detection."""
    src = tmp_path / "src"
    pkg = src / pkg_name
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").touch()
    return src


class TestClassifyModuleRole:
    """Verify orchestrator vs leaf classification based on sibling diversity."""

    @pytest.mark.parametrize(
        ("module", "imports", "expected"),
        [
            pytest.param(
                "pkg.core.rules.quality",
                ["pkg.core.rules.a", "pkg.core.rules.b", "pkg.core.rules.c"],
                "orchestrator",
                id="orchestrator_3_siblings",
            ),
            pytest.param(
                "pkg.core.rules.quality",
                ["pkg.core.rules.a", "pkg.core.rules.b"],
                "leaf",
                id="leaf_2_siblings",
            ),
            pytest.param(
                "pkg.core.rules.quality",
                ["os", "pathlib", "typing", "pkg.core.rules.a"],
                "leaf",
                id="ignores_external_imports",
            ),
            pytest.param(
                "pkg.module_x",
                ["pkg.module_a", "pkg.module_b", "pkg.module_c"],
                "leaf",
                id="flat_package_all_leaf",
            ),
            pytest.param(
                "pkg.a.b.c.f",
                ["pkg.a.b.c.d", "pkg.a.b.c.e"],
                "leaf",
                id="one_deep_subpackage_2_siblings",
            ),
        ],
    )
    def test_classify_module_role(
        self,
        tmp_path: Path,
        module: str,
        imports: list[str],
        expected: str,
    ) -> None:
        """classify_module_role: orchestrator iff >=3 distinct sibling imports."""
        from axm_audit.core.rules.architecture.coupling import classify_module_role

        src_path = _make_pkg(tmp_path, "pkg")
        result = classify_module_role(module, imports, src_path)
        assert result == expected
