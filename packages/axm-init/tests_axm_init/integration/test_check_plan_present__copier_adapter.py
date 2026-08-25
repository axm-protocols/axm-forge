"""Integration: rendered paper template vs. the plan check, on the real FS.

Every assertion here is filesystem-case independent (literal string
comparison and exact membership in ``iterdir()``, never ``Path.exists()``),
so a case-insensitive macOS volume cannot mask a case divergence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.checks.paper import _PLAN_FILENAME, check_plan_present
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration


def _render_paper(destination: Path, *, has_package: bool) -> Path:
    """Render the bundled paper template into *destination* via the adapter."""
    data: dict[str, object] = {
        "paper_name": "attention-study",
        "title": "Attention Study",
        "author": "Tester",
        "has_package": has_package,
    }
    if has_package:
        data["package_name"] = "attention_study"

    result = CopierAdapter().copy(
        CopierConfig(
            template_path=get_template_path(TemplateType.PAPER),
            destination=destination,
            data=data,
            trust_template=True,
        )
    )

    assert result.success is True, result.message
    return destination


def _root_entries(root: Path) -> set[str]:
    """The exact entry names of *root*, with their rendered case preserved."""
    return {entry.name for entry in root.iterdir()}


def test_autonomous_paper_render_holds_the_expected_plan_filename(
    tmp_path: Path,
) -> None:
    """AC2: an autonomous paper (own package) renders the plan name the check
    expects, and the check passes on that rendered root."""
    root = _render_paper(tmp_path / "autonomous", has_package=True)

    assert _PLAN_FILENAME in _root_entries(root)
    assert check_plan_present(root).passed is True


def test_satellite_paper_render_holds_the_expected_plan_filename(
    tmp_path: Path,
) -> None:
    """AC2: a satellite paper (no embedded package) renders the very same plan
    name, and the check passes on it too."""
    root = _render_paper(tmp_path / "satellite", has_package=False)

    assert _PLAN_FILENAME in _root_entries(root)
    assert check_plan_present(root).passed is True


def test_missing_plan_diagnostic_names_the_canonical_uppercase_filename(
    tmp_path: Path,
) -> None:
    """AC3: on a paper root carrying no plan file at all, the message and the
    fix name PLAN.md and never the lowercase form."""
    root = tmp_path / "paper-without-plan"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-x"\n\n[tool.axm-lab]\nslug = "paper-x"\n',
        encoding="utf-8",
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper X\n", encoding="utf-8")

    result = check_plan_present(root)
    blob = f"{result.message} {result.fix}"

    assert result.passed is False
    assert "PLAN.md" in blob
    assert "plan.md" not in blob
