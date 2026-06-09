"""Integration tests for CheckEngine exclusion-by-displayed-name (AXM-1840).

The canonical name carried by ``CheckResult.name`` (hand-set inside each check
function, e.g. ``pyproject.urls``) must be the single source of truth for
exclusion matching. Excluding a check by its DISPLAYED name must actually skip
it, and the excluded-result stamp must carry that same canonical name.

The ``pyproject.urls`` check is the canary: its function name is
``check_pyproject_urls`` so the legacy inferred name was
``pyproject.pyproject_urls`` (divergent from the displayed ``pyproject.urls``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine

pytestmark = pytest.mark.integration


def _exclude_pyproject_urls(project: Path) -> None:
    """Append a ``[tool.axm-init].exclude`` of the displayed name to pyproject."""
    pyproject = project / "pyproject.toml"
    content = pyproject.read_text()
    content += '\n[tool.axm-init]\nexclude = ["pyproject.urls"]\n'
    pyproject.write_text(content)


def test_exclusion_by_displayed_name_skips_check(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """AC2: excluding by the displayed name ``pyproject.urls`` removes it.

    The check must not appear as an active (executed) result and must be
    recorded in ``excluded_checks``.
    """
    project = gold_project__from_check_engine_run_and_format
    _exclude_pyproject_urls(project)

    result = CheckEngine(project).run()

    # The displayed name was excluded by config -> recorded as excluded.
    assert "pyproject.urls" in result.excluded_checks
    # And the legacy inferred name must NOT leak into excluded_checks.
    assert "pyproject.pyproject_urls" not in result.excluded_checks

    # The check still surfaces (as an auto-pass excluded stamp), never as a
    # freshly executed result with a real weight/message.
    matching = [c for c in result.checks if c.name == "pyproject.urls"]
    assert len(matching) == 1
    assert matching[0].message == "Excluded by config"


def test_excluded_result_uses_canonical_name(
    gold_project__from_check_engine_run_and_format: Path,
) -> None:
    """AC3: the excluded-result stamp carries the canonical displayed name.

    Excluding ``pyproject.urls`` must produce a ``CheckResult`` whose ``name``
    is exactly ``pyproject.urls`` (not the inferred ``pyproject.pyproject_urls``).
    """
    project = gold_project__from_check_engine_run_and_format
    _exclude_pyproject_urls(project)

    result = CheckEngine(project).run()

    excluded = [c for c in result.checks if c.message == "Excluded by config"]
    excluded_names = {c.name for c in excluded}
    assert "pyproject.urls" in excluded_names
    assert "pyproject.pyproject_urls" not in excluded_names

    stamp = next(c for c in excluded if c.name == "pyproject.urls")
    assert stamp.passed is True
    assert stamp.category == "pyproject"
