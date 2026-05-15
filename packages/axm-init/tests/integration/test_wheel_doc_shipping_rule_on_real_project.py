"""Integration tests: wheel-doc-shipping check driven via CheckEngine (AXM-1715)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine

pytestmark = pytest.mark.integration


def _scaffold(project: Path, *, with_force_include: bool) -> None:
    force_include_block = (
        "[tool.hatch.build.targets.wheel.force-include]\n"
        '"docs/test_quality.md" = "pkg/docs/test_quality.md"\n'
        if with_force_include
        else ""
    )
    (project / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "pkg"

            [tool.axm-init.wheel-doc]
            files = ["docs/test_quality.md"]

            [tool.hatch.build.targets.wheel]
            packages = ["src/pkg"]

            {force_include_block}
            """
        ).lstrip()
    )
    docs = project / "docs"
    docs.mkdir()
    (docs / "test_quality.md").write_text("# test quality\n")


def _find_result(project_result: object, check_name: str) -> object:
    results = getattr(project_result, "results", None) or getattr(
        project_result, "checks", []
    )
    for r in results:
        if getattr(r, "name", None) == check_name:
            return r
    raise AssertionError(f"check {check_name!r} not found in result")


def test_axm_init_check_passes_on_correctly_wired_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, with_force_include=True)

    engine = CheckEngine(tmp_path)
    project_result = engine.run()

    finding = _find_result(project_result, "pyproject.wheel_doc_shipping")
    assert finding.passed is True


def test_axm_init_check_fails_on_orphan_docs(tmp_path: Path) -> None:
    _scaffold(tmp_path, with_force_include=False)

    engine = CheckEngine(tmp_path)
    project_result = engine.run()

    finding = _find_result(project_result, "pyproject.wheel_doc_shipping")
    assert finding.passed is False
    assert any("test_quality.md" in d for d in finding.details)
