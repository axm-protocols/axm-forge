"""Node docs gold-standard checks — MkDocs prose (reused) + TypeDoc API ref.

The Python docs checks split into two concerns, and only one is Python-specific:

* **Prose docs** (tutorials / how-to / explanation — the Diataxis tree served by
  MkDocs) are *language-agnostic*: MkDocs renders Markdown regardless of the
  code beneath it. So the node project reuses the SAME MkDocs + Diataxis
  convention as Python — one tool, one structure across the whole AXM stack.
* **API reference** is the only delta: Python uses mkdocstrings (reads Python
  docstrings); node uses TypeDoc (reads TSDoc). The node check accepts a TypeDoc
  config in place of mkdocstrings.

This keeps the docs convention harmonized (MkDocs everywhere) and adapts only
the auto-generated API-reference layer.
"""

from __future__ import annotations

import json
from pathlib import Path

from axm_init.models.check import CheckResult

__all__ = ["check_api_reference", "check_mkdocs_exists"]


def check_mkdocs_exists(project: Path) -> CheckResult:
    """Check: a MkDocs site is configured (reused as-is from the Python standard).

    MkDocs is language-agnostic prose docs, so node projects use the same
    ``mkdocs.yml`` + ``docs/`` Diataxis tree as Python projects.
    """
    if (project / "mkdocs.yml").is_file() or (project / "mkdocs.yaml").is_file():
        return CheckResult(
            name="docs.mkdocs_exists",
            category="docs",
            passed=True,
            weight=3,
            message="MkDocs configured",
            details=[],
            fix="",
        )
    return CheckResult(
        name="docs.mkdocs_exists",
        category="docs",
        passed=False,
        weight=3,
        message="No mkdocs.yml",
        details=["Prose docs use MkDocs + Diataxis (same as Python projects)"],
        fix="Add a mkdocs.yml with a Diataxis docs/ tree.",
    )


def _has_typedoc(project: Path) -> bool:
    """Return True if TypeDoc is configured (config file or devDependency)."""
    for name in ("typedoc.json", "typedoc.config.js", "typedoc.config.cjs"):
        if (project / name).is_file():
            return True
    pkg = project / "package.json"
    if not pkg.is_file():
        return False
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    if "typedoc" in data:
        return True
    dev = data.get("devDependencies")
    return isinstance(dev, dict) and "typedoc" in dev


def check_api_reference(project: Path) -> CheckResult:
    """Check: an auto-generated API reference is configured (TypeDoc).

    The node delta over the shared MkDocs prose docs: TypeDoc replaces
    mkdocstrings as the TSDoc-driven API-reference generator.
    """
    if _has_typedoc(project):
        return CheckResult(
            name="docs.api_reference",
            category="docs",
            passed=True,
            weight=2,
            message="TypeDoc API reference configured",
            details=[],
            fix="",
        )
    return CheckResult(
        name="docs.api_reference",
        category="docs",
        passed=False,
        weight=2,
        message="No TypeDoc API reference",
        details=["TypeDoc generates the API reference from TSDoc comments"],
        fix="Add typedoc + a typedoc.json to generate the API reference.",
    )
