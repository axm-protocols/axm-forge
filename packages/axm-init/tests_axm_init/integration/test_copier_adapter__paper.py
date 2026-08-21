"""Integration: the rendered paper template vs the research protocol document.

Every fixture here is a REAL render of the bundled ``paper-submodule`` Copier
template through the public :class:`CopierAdapter` — never a hand-built tree —
so each assertion witnesses what a freshly scaffolded paper carries on disk.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.checks.paper import check_research_present
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

RESEARCH_FILENAME = "RESEARCH.md"
TODO_MARKER = "TODO"
GAP_STATEMENT = "No one has measured attention sinks under 4-bit quantisation."
_STATUS_LINE = re.compile(r"^\s*(?:#\s*)?-?\s*status\s*:", re.IGNORECASE)


def _render_paper(
    destination: Path,
    *,
    gap_statement: str = GAP_STATEMENT,
) -> Path:
    """Render the paper template into *destination* and return that root."""
    destination.mkdir(parents=True, exist_ok=True)
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.PAPER),
            destination=destination,
            data={
                "paper_name": "attention-study",
                "title": "Attention Study",
                "author": "Test Author",
                "has_package": True,
                "package_name": "attention_study",
                "gap_statement": gap_statement,
            },
            defaults=True,
            overwrite=True,
        )
    )
    assert result.success, result.message
    return destination


def _split_front_matter(text: str) -> tuple[str, str]:
    """Split a ``---`` delimited document into (front-matter, body)."""
    assert text.startswith("---"), text[:120]
    _, raw_header, body = text.split("---", 2)
    return raw_header, body


def _read_research(root: Path) -> tuple[str, str]:
    """Return the (front-matter, body) halves of the rendered document."""
    return _split_front_matter((root / RESEARCH_FILENAME).read_text(encoding="utf-8"))


def test_rendered_paper_carries_the_research_document_at_its_root(
    tmp_path: Path,
) -> None:
    """AC1: RESEARCH.md renders at the paper root, beside paper/ — not inside."""
    root = _render_paper(tmp_path / "paper-root")

    names = {entry.name for entry in root.iterdir()}

    assert RESEARCH_FILENAME in names, sorted(names)
    assert (root / RESEARCH_FILENAME).is_file()
    assert (root / "paper").is_dir(), sorted(names)
    assert not (root / "paper" / RESEARCH_FILENAME).exists()
    assert not (root / "experiments" / RESEARCH_FILENAME).exists()
    assert not (root / "PROTOCOL.md").exists(), sorted(names)


def test_rendered_front_matter_declares_gap_and_investigations_only(
    tmp_path: Path,
) -> None:
    """AC2: exactly {gap, investigations}, each entry well formed, no claim."""
    root = _render_paper(tmp_path / "paper-root")

    raw_header, _ = _read_research(root)
    header = yaml.safe_load(raw_header)

    assert isinstance(header, dict), raw_header
    assert set(header) == {"gap", "investigations"}, sorted(header)
    gap = header["gap"]
    assert isinstance(gap, dict), gap
    assert isinstance(gap.get("statement"), str), gap
    assert gap["statement"].strip(), gap
    assert isinstance(gap.get("references"), list), gap
    investigations = header["investigations"]
    assert isinstance(investigations, list), investigations
    assert investigations, header
    for entry in investigations:
        assert isinstance(entry, dict), entry
        assert {"id", "objective", "experiments"} <= set(entry), sorted(entry)
        assert "claim" not in entry, sorted(entry)


def test_no_rendered_investigation_declares_a_status(tmp_path: Path) -> None:
    """AC3: no status key on an investigation, no active status line either."""
    root = _render_paper(tmp_path / "paper-root")

    raw_header, _ = _read_research(root)
    header = yaml.safe_load(raw_header)

    assert isinstance(header, dict), raw_header
    investigations = header.get("investigations")
    assert isinstance(investigations, list), header
    assert [e for e in investigations if "status" in e] == []
    offending = [ln for ln in raw_header.splitlines() if _STATUS_LINE.match(ln)]
    assert offending == [], offending


def test_gap_answer_is_propagated_and_empty_sections_are_marked(
    tmp_path: Path,
) -> None:
    """AC4: the Copier gap answer lands verbatim in statement; body says TODO."""
    answer = "Nobody has quantified sink drift across quantisation regimes."
    root = _render_paper(tmp_path / "paper-root", gap_statement=answer)

    raw_header, body = _read_research(root)
    header = yaml.safe_load(raw_header)

    assert isinstance(header, dict), raw_header
    assert header["gap"]["statement"] == answer
    assert TODO_MARKER in body, body


def test_freshly_rendered_paper_passes_the_research_form_check(
    tmp_path: Path,
) -> None:
    """AC5: the research form check is green straight off the template."""
    root = _render_paper(tmp_path / "paper-root")

    result = check_research_present(root)

    assert result.passed is True, result.message
