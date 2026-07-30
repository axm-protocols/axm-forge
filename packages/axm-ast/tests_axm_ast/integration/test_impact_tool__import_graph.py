"""Integration tests for the ``ast_impact`` tool reverse-import opt-in.

Exercises ``ImpactTool.execute(..., include_module_importers=True)`` against a
real on-disk package where a file only ``import pkg.shim`` a re-export shim of
the edited symbol's module -- a dependent a symbol-level traversal misses.

Asserts three contracts:
- AC1: with the opt-in on, the module-only importer surfaces through the tool.
- AC2: with the opt-in off (default), the ToolResult data/text are unchanged --
  the ``module_level_importers`` field is absent and the opt-in adds *only*
  that field.
- AC1: ``execute`` forwards the toggle to the core function verbatim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from axm_ast.tools.impact import ImpactTool


def _write_shim_pkg(root: Path) -> Path:
    """Write a package where ``c`` imports a shim re-exporting ``m``.

    Layout::

        mypkg/m.py     -> defines ``target``
        mypkg/shim.py  -> ``from mypkg.m import target`` (re-export shim)
        mypkg/c.py     -> ``import mypkg.shim`` (imports the shim, not target)

    ``c`` reaches ``target``'s module only transitively, through the shim -- a
    dependency a symbol-level call-graph traversal cannot see.
    """
    pkg = root / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "m.py").write_text("def target() -> int:\n    return 1\n")
    (pkg / "shim.py").write_text("from mypkg.m import target\n\n__all__ = ['target']\n")
    (pkg / "c.py").write_text("import mypkg.shim\n")
    return pkg


@pytest.mark.integration
def test_opt_in_surfaces_module_only_importer(tmp_path: Path) -> None:
    """AC1: opt-in surfaces a module-only importer through the tool."""
    pkg = _write_shim_pkg(tmp_path)

    out = ImpactTool().execute(
        path=str(pkg),
        symbol="target",
        include_module_importers=True,
    )

    assert out.success is True
    importers = out.data["module_level_importers"]
    assert isinstance(importers, list)
    # The file importing the shim is surfaced as a module-level importer.
    assert "c" in importers
    # The shim itself (a direct importer of the module) is surfaced too.
    assert "shim" in importers


@pytest.mark.integration
def test_default_omits_field_and_opt_in_adds_only_that_field(
    tmp_path: Path,
) -> None:
    """AC2: default result unchanged; opt-in adds ONLY module_level_importers."""
    pkg = _write_shim_pkg(tmp_path)
    tool = ImpactTool()

    default = tool.execute(path=str(pkg), symbol="target")
    opt_in = tool.execute(path=str(pkg), symbol="target", include_module_importers=True)

    # Default output never carries the opt-in field (byte-for-byte legacy).
    assert "module_level_importers" not in default.data
    # The opt-in run does carry it, and it is the ONLY difference in the data.
    assert "c" in opt_in.data["module_level_importers"]
    reduced = {k: v for k, v in opt_in.data.items() if k != "module_level_importers"}
    assert reduced == default.data
    # Rendered text is unchanged -- the field is data-only.
    assert opt_in.text == default.text


@pytest.mark.integration
def test_execute_forwards_toggle_to_core(tmp_path: Path) -> None:
    """AC1: execute forwards include_module_importers verbatim to the core."""
    pkg = _write_shim_pkg(tmp_path)
    captured: dict[str, Any] = {}

    def _fake_analyze(path: Path, symbol: str, **kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "symbol": symbol,
            "definition": {"file": "m.py", "line": 1},
            "score": "LOW",
            "callers": [],
            "module_level_importers": ["c", "shim"],
        }

    with (
        patch(
            "axm_ast.core.impact.analyze_impact_workspace",
            side_effect=ValueError,
        ),
        patch("axm_ast.core.impact.analyze_impact", side_effect=_fake_analyze),
    ):
        out = ImpactTool().execute(
            path=str(pkg),
            symbol="target",
            include_module_importers=True,
        )

    assert captured.get("include_module_importers") is True
    assert out.success is True
    assert out.data["module_level_importers"] == ["c", "shim"]
