"""Integration tests for the RESEARCH.md form check on a paper folder."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from axm_init.checks import paper as paper_checks
from axm_init.core.checker import CheckEngine, validate_context_tables

if TYPE_CHECKING:
    from collections.abc import Callable

    from axm_init.models.check import CheckResult

pytestmark = pytest.mark.integration

_RESEARCH_FILENAME = "RESEARCH.md"
_RESEARCH_CHECK_ID = "paper.research_present"

_RESEARCH_SHAPED = (
    '---\ngap:\n  statement: "x"\n  references: []\ninvestigations: []\n---\n\n'
    "# Research\n"
)
_FOREIGN_KEYS = "---\nfoo: bar\n---\n\n# Research\n"
_NO_HEADER = "# titre\n\nJust prose.\n"
_EMPTY_HEADER = "---\n---\n"


def _research_check() -> Callable[[Path], CheckResult]:
    """The paper check grading the research protocol document."""
    check: Callable[[Path], CheckResult] | None = getattr(
        paper_checks, "check_research_present", None
    )
    assert check is not None, "axm_init.checks.paper must expose check_research_present"
    return check


def _paper(root: Path) -> Path:
    """Build a complete paper folder on disk, carrying no RESEARCH.md."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-r"\nversion = "0.1.0"\n\n'
        '[tool.axm-lab]\nslug = "paper-r"\n',
        encoding="utf-8",
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper R\n", encoding="utf-8")
    (root / "PIPELINE.md").write_text("# Pipeline\n", encoding="utf-8")
    (root / "PLAN.md").write_text(
        "---\ntitle: Paper R\nstatus: draft\n---\n\n# Plan\n", encoding="utf-8"
    )
    return root


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_RESEARCH_SHAPED, id="ac1_research_shaped_header"),
        pytest.param(_FOREIGN_KEYS, id="ac5_foreign_keys_only"),
    ],
)
def test_non_empty_front_matter_passes(tmp_path: Path, document: str) -> None:
    """AC1/AC5: any non-empty front-matter passes - the check grades the FORM.

    A header carrying only foreign keys passes exactly like a research-shaped
    one: the check never reads ``gap``, ``investigations`` or a status.
    """
    project = _paper(tmp_path / "paper-r")
    (project / _RESEARCH_FILENAME).write_text(document, encoding="utf-8")

    result = _research_check()(project)

    assert result.passed is True
    assert result.category == "paper"


def test_missing_document_fix_names_the_expected_file(tmp_path: Path) -> None:
    """AC2: with no RESEARCH.md the check fails and its fix names the file."""
    project = _paper(tmp_path / "paper-r")

    result = _research_check()(project)

    assert result.passed is False
    assert _RESEARCH_FILENAME in result.fix


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_NO_HEADER, id="ac3_no_front_matter"),
        pytest.param(_EMPTY_HEADER, id="ac3_empty_front_matter"),
    ],
)
def test_absent_or_empty_front_matter_fails(tmp_path: Path, document: str) -> None:
    """AC3: a document with no header, or with an empty one, is refused."""
    project = _paper(tmp_path / "paper-r")
    (project / _RESEARCH_FILENAME).write_text(document, encoding="utf-8")

    result = _research_check()(project)

    assert result.passed is False


def test_engine_plays_the_research_check_on_a_paper(tmp_path: Path) -> None:
    """AC4: the engine discovers the check for the paper context.

    The context tables must also stay valid - an id registered nowhere makes
    ``validate_context_tables()`` raise.
    """
    project = _paper(tmp_path / "paper-r")
    (project / _RESEARCH_FILENAME).write_text(_RESEARCH_SHAPED, encoding="utf-8")

    validate_context_tables()
    result = CheckEngine(project).run()

    executed = {check.name: check for check in result.checks}
    assert _RESEARCH_CHECK_ID in executed, sorted(executed)
    assert executed[_RESEARCH_CHECK_ID].passed is True
