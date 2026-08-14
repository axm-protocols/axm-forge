"""Integration: rendering the paper-submodule template via CopierAdapter.

Real I/O: every test renders the packaged template into ``tmp_path`` through
the public :class:`CopierAdapter` boundary and asserts on the produced tree.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

PACKAGE_ANSWERS: Mapping[str, object] = {
    "paper_name": "attention-study",
    "title": "A Study of Attention",
    "author": "Ada Lovelace",
    "has_package": True,
    "package_name": "attention_study",
}

SATELLITE_ANSWERS: Mapping[str, object] = {
    "paper_name": "attention-study",
    "title": "A Study of Attention",
    "author": "Ada Lovelace",
    "has_package": False,
}

PACKAGE_GOLDEN: frozenset[str] = frozenset(
    {
        ".gitignore",
        "README.md",
        "PLAN.md",
        "PIPELINE.md",
        "pyproject.toml",
        "src/attention_study/__init__.py",
        "paper/main.tex",
        "paper/references.bib",
        "paper/Makefile",
        "experiments/.gitkeep",
    }
)

CACHE_DIRS: tuple[str, ...] = ("__pycache__", ".mypy_cache", ".ruff_cache")


def _render(
    destination: Path,
    answers: Mapping[str, object],
    template_path: Path | None = None,
) -> Path:
    """Render the paper template into *destination* and return it."""
    source = template_path or Path(get_template_path(TemplateType.PAPER))
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=source,
            destination=destination,
            data=answers,
            defaults=True,
            overwrite=True,
        )
    )
    assert result.success, result.message
    return destination


def _rendered_files(root: Path) -> set[str]:
    """Relative paths of rendered files, minus copier bookkeeping."""
    return {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not p.name.startswith(".copier-answers")
    }


def test_package_flavour_renders_autonomous_paper(tmp_path: Path) -> None:
    """AC2: the package flavour renders exactly the autonomous paper tree and
    no generated experiment index file."""
    root = _render(tmp_path / "pkg", PACKAGE_ANSWERS)
    files = _rendered_files(root)
    assert files == set(PACKAGE_GOLDEN)
    assert not [f for f in files if Path(f).name.lower().startswith("index")]


def test_satellite_flavour_renders_without_package(tmp_path: Path) -> None:
    """AC3: the satellite flavour drops the manifest and the src layout while
    keeping the readme, the plan and the LaTeX main source."""
    root = _render(tmp_path / "sat", SATELLITE_ANSWERS)
    assert not (root / "pyproject.toml").exists()
    assert not (root / "src").exists()
    assert (root / "README.md").is_file()
    assert (root / "PLAN.md").is_file()
    assert (root / "paper" / "main.tex").is_file()


def test_plan_document_carries_yaml_front_matter(tmp_path: Path) -> None:
    """AC4: PLAN.md opens on a triple-dash YAML block holding the answers."""
    root = _render(tmp_path / "plan", PACKAGE_ANSWERS)
    text = (root / "PLAN.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front_matter = text.split("---", 2)[1]
    assert "attention-study" in front_matter
    assert "A Study of Attention" in front_matter
    assert "Ada Lovelace" in front_matter


def test_caches_are_excluded_from_render(tmp_path: Path) -> None:
    """AC5: cache directories and macOS metadata present in the template source
    never reach the rendered tree."""
    source = tmp_path / "template_src"
    shutil.copytree(Path(get_template_path(TemplateType.PAPER)), source)
    for cache in CACHE_DIRS:
        (source / cache).mkdir(parents=True, exist_ok=True)
        (source / cache / "stale.bin").write_text("x", encoding="utf-8")
    (source / ".DS_Store").write_text("x", encoding="utf-8")

    root = _render(tmp_path / "clean", PACKAGE_ANSWERS, template_path=source)

    rendered = [p.relative_to(root) for p in root.rglob("*")]
    assert rendered
    for rel in rendered:
        assert not set(rel.parts) & set(CACHE_DIRS), rel
        assert rel.name != ".DS_Store", rel


def test_render_carries_its_paper_marker(tmp_path: Path) -> None:
    """AC6: the package render marks itself via the axm-lab tool section; the
    satellite render marks itself structurally instead."""
    package_root = _render(tmp_path / "marker_pkg", PACKAGE_ANSWERS)
    manifest = (package_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.axm-lab" in manifest

    satellite_root = _render(tmp_path / "marker_sat", SATELLITE_ANSWERS)
    assert (satellite_root / "paper").is_dir()
    assert (satellite_root / "experiments").is_dir()
    assert (satellite_root / "README.md").is_file()
    assert not (satellite_root / "pyproject.toml").exists()
