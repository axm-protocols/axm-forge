"""Integration tests for the decoupled axm-mcp discovery shell.

axm-mcp must stay a thin discovery shell: its app/discovery modules must
not import axm *core* business logic, and must not declare the private
orchestrator packages as hard deps.

These invariants need real filesystem reads — each imported module's live
``__file__`` source and the package's ``pyproject.toml`` — so they live at
the integration tier. The pure import/attribute decoupling checks (no
hardcoded protocol funcs, dynamic discovery seam, legacy ``server/`` gone)
are unit-level and live in ``tests/unit/test_mcp_app.py``.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from axm_mcp import discovery, mcp_app

pytestmark = pytest.mark.integration


def _imports_axm_core(module: ModuleType) -> bool:
    """True if the imported module imports from the ``axm`` core namespace."""
    assert module.__file__ is not None
    tree = ast.parse(Path(module.__file__).read_text())
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == "axm" or node.module.startswith("axm."))
        for node in ast.walk(tree)
    )


class TestDecouplingFromSource:
    """Source-level decoupling invariants on the discovery shell modules."""

    @pytest.mark.parametrize(
        "module",
        [discovery, mcp_app],
        ids=["discovery", "mcp_app"],
    )
    def test_no_axm_core_import(self, module: ModuleType) -> None:
        """The imported module pulls nothing under the ``axm.`` core namespace."""
        assert not _imports_axm_core(module), f"{module.__name__} imports from axm core"

    def test_no_private_hard_dependencies(self) -> None:
        """pyproject.toml lists neither axm-nexus nor axm-engine as hard deps."""
        # Reference both shell modules so this file's canonical tuple stays
        # (discovery, mcp_app) — the package root is resolved from either's
        # live ``__file__`` (src/axm_mcp/<mod>.py → package root is parents[2]).
        assert discovery.__file__ is not None
        assert mcp_app.__file__ is not None
        pyproject_path = Path(mcp_app.__file__).parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text())
        deps = data.get("project", {}).get("dependencies", [])

        # axm (public thin wrapper) is allowed — axm-nexus/axm-engine are not.
        private_pkgs = {"axm-nexus", "axm-engine"}
        for dep in deps:
            raw = dep.split(">")[0].split("<")[0]
            dep_name = raw.split("=")[0].split("[")[0].strip()
            assert dep_name not in private_pkgs, (
                f"Private package is a hard dependency: {dep}"
            )
