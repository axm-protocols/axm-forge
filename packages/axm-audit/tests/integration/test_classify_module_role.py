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
