"""Integration: the really rendered paper template vs the paper structure check.

The fixtures here are not hand-built trees: they are produced by running the
bundled ``paper-submodule`` Copier template through the public
:class:`CopierAdapter`, for the two legitimate flavours of a paper (autonomous,
shipping its own Python package, and satellite, without one).
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.checks.paper import check_paper_structure
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

PIPELINE_FILENAME = "PIPELINE.md"


def _render_paper(destination: Path, *, has_package: bool) -> Path:
    """Render the paper template into *destination* and return that root."""
    destination.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {
        "paper_name": "attention-study",
        "title": "Attention Study",
        "author": "Test Author",
        "has_package": has_package,
    }
    if has_package:
        data["package_name"] = "attention_study"
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.PAPER),
            destination=destination,
            data=data,
            defaults=True,
            overwrite=True,
        )
    )
    assert result.success, result.message
    return destination


def _deaccent(text: str) -> str:
    """Fold accents away so a heading matches whatever its spelling carries."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def test_rendered_autonomous_paper_carries_the_provenance_document(
    tmp_path: Path,
) -> None:
    """AC2: an autonomous paper renders PIPELINE.md as a file at its root."""
    root = _render_paper(tmp_path / "autonomous", has_package=True)

    names = {entry.name for entry in root.iterdir()}

    assert PIPELINE_FILENAME in names, sorted(names)
    assert (root / PIPELINE_FILENAME).is_file()


def test_rendered_satellite_paper_carries_the_provenance_document(
    tmp_path: Path,
) -> None:
    """AC2: a satellite paper renders the same PIPELINE.md at its root."""
    root = _render_paper(tmp_path / "satellite", has_package=False)

    names = {entry.name for entry in root.iterdir()}

    assert PIPELINE_FILENAME in names, sorted(names)
    assert (root / PIPELINE_FILENAME).is_file()


def test_rendered_paper_stripped_of_its_provenance_document_fails_the_check(
    tmp_path: Path,
) -> None:
    """AC1: a rendered paper deprived of PIPELINE.md fails, naming it."""
    root = _render_paper(tmp_path / "autonomous", has_package=True)
    (root / PIPELINE_FILENAME).unlink()

    result = check_paper_structure(root)

    assert result.passed is False
    assert PIPELINE_FILENAME in f"{result.message} {result.fix}"


def test_rendered_provenance_document_invites_documenting_the_data(
    tmp_path: Path,
) -> None:
    """AC3: the rendered skeleton carries the three provenance sections and a
    delimited command block to fill in."""
    root = _render_paper(tmp_path / "autonomous", has_package=True)

    text = (root / PIPELINE_FILENAME).read_text(encoding="utf-8")
    folded = _deaccent(text)

    assert "## origine des donnees" in folded
    assert "## perimetre" in folded
    assert "## commande de reproduction" in folded
    assert text.count("```") >= 2
