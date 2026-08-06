"""Doc-coherence tests for the ``docs/index.md`` entry point.

The documentation index must advertise the near-miss diagnostics module and
the invisible-character markers it renders. Importing the public entry point
:func:`axm_edit.core.diagnostics.explain_near_miss` makes a rename break these
tests instead of silently rotting the docs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_edit.core.diagnostics import explain_near_miss

PACKAGE_ROOT = Path(__file__).parents[2]
INDEX_MD = PACKAGE_ROOT / "docs" / "index.md"


def _section_lines(text: str, token: str) -> list[str]:
    """Return the body lines of the first section whose heading holds ``token``.

    Heading detection is deliberately lenient (any ``#`` level, any decoration
    around the token) so the assertions target the section content, not the
    exact heading spelling.
    """
    collected: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            inside = token in line.lower()
            continue
        if inside:
            collected.append(line)
    return collected


@pytest.fixture
def index_text() -> str:
    """The raw contents of the packaged ``docs/index.md``."""
    return INDEX_MD.read_text(encoding="utf-8")


@pytest.mark.integration
def test_docs_index_modules_table_lists_core_diagnostics(index_text: str) -> None:
    """AC1: the Modules table links ``axm_edit.core.diagnostics`` and names it.

    Exactly one row mentions the module, links its API reference page and
    names the public ``explain_near_miss`` entry point.
    """
    rows = [
        line
        for line in _section_lines(index_text, "modules")
        if line.lstrip().startswith("|")
    ]
    matching = [row for row in rows if "axm_edit.core.diagnostics" in row]
    assert len(matching) == 1, (
        "expected exactly one Modules row for axm_edit.core.diagnostics, "
        f"found {len(matching)}"
    )
    row = matching[0]
    assert "reference/api/axm_edit/core/diagnostics.md" in row, row
    assert explain_near_miss.__name__ in row, row


@pytest.mark.integration
def test_docs_index_features_advertise_near_miss_markers(index_text: str) -> None:
    """AC2: a Features bullet describes the near-miss report markers.

    At least one bullet of the Features list carries both the ``<TAB>`` and
    ``<SP>`` marker literals rendered by the near-miss replace report.
    """
    bullets = [
        line
        for line in _section_lines(index_text, "features")
        if line.lstrip().startswith("- ")
    ]
    marker_bullets = [
        bullet for bullet in bullets if "<TAB>" in bullet and "<SP>" in bullet
    ]
    assert marker_bullets, (
        "expected a Features bullet naming both the <TAB> and <SP> markers, "
        f"got {bullets!r}"
    )
