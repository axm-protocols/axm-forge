"""Paper checks — the invariants of a research paper, not of a package.

A paper carries none of a Python distribution's invariants (no Diataxis
mkdocs, no Trusted Publishing, no CI matrix) but has its own: a ``paper/``
directory, an ``experiments/`` directory, a README, and a plan document
declaring the intention through a YAML front-matter header.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_init.models.check import CheckResult

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["check_paper_structure", "check_plan_present"]

#: Delimiter opening and closing a YAML front-matter block.
_FRONT_MATTER_DELIMITER = "---"

#: Plan document, relative to the paper root.
_PLAN_FILENAME = "PLAN.md"


def _parse_front_matter(text: str) -> dict[str, str] | None:
    """Parse the YAML front-matter block of *text*, if it carries one.

    Pure helper: it takes the document text, never a path, so the parsing
    rule is testable without touching the filesystem.

    Args:
        text: Full document text.

    Returns:
        The parsed ``key: value`` mapping for a triple-dash delimited
        header, or ``None`` when *text* opens with no such header (or when
        the block is never closed).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONT_MATTER_DELIMITER:
        return None

    parsed: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == _FRONT_MATTER_DELIMITER:
            return parsed
        key, separator, value = line.partition(":")
        if separator and key.strip():
            parsed[key.strip()] = value.strip()
    return None


def check_paper_structure(project: Path) -> CheckResult:
    """Check: the paper carries paper/, experiments/ and a README.

    Args:
        project: Paper root directory.

    Returns:
        A failed ``CheckResult`` naming every missing entry, or a passed one.
    """
    entries = (
        ("paper/", (project / "paper").is_dir()),
        ("experiments/", (project / "experiments").is_dir()),
        ("README.md", (project / "README.md").is_file()),
    )
    missing = [label for label, present in entries if not present]
    if missing:
        return CheckResult(
            name="paper.paper_structure",
            category="paper",
            passed=False,
            weight=5,
            message=f"Paper layout missing {len(missing)} entry(ies)",
            details=[f"Missing: {', '.join(missing)}"],
            fix="Create paper/, experiments/ and README.md at the paper root.",
        )
    return CheckResult(
        name="paper.paper_structure",
        category="paper",
        passed=True,
        weight=5,
        message="Paper layout complete (paper/, experiments/, README.md)",
        details=[],
        fix="",
    )


def check_plan_present(project: Path) -> CheckResult:
    """Check: the plan document exists and declares a front-matter header.

    Args:
        project: Paper root directory.

    Returns:
        A failed ``CheckResult`` when ``PLAN.md`` is missing or carries no
        non-empty YAML front-matter, a passed one otherwise.
    """
    path = project / _PLAN_FILENAME
    front_matter = (
        _parse_front_matter(path.read_text(encoding="utf-8"))
        if path.is_file()
        else None
    )
    if not front_matter:
        reason = (
            f"{_PLAN_FILENAME} not found"
            if not path.is_file()
            else f"{_PLAN_FILENAME} carries no YAML front-matter"
        )
        return CheckResult(
            name="paper.plan_present",
            category="paper",
            passed=False,
            weight=5,
            message=reason,
            details=[],
            fix=(
                f"Write {_PLAN_FILENAME} opening with a '---' delimited "
                "YAML header declaring the paper intention."
            ),
        )
    return CheckResult(
        name="paper.plan_present",
        category="paper",
        passed=True,
        weight=5,
        message=f"{_PLAN_FILENAME} declares a front-matter header",
        details=[],
        fix="",
    )
