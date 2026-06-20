"""Integration: scaffold a node/svelte project, then gold-standard-check it.

Proves the full loop end to end on the real bundled Copier templates: a project
scaffolded with ``framework=<fw>`` is auto-detected as that framework and passes
its own gold-standard checks (node base, plus the svelte delta for svelte).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine
from axm_init.core.framework import Framework
from axm_init.tools.scaffold import InitScaffoldTool


def _scaffold(tmp_path: Path, framework: str) -> Path:
    """Scaffold a project of *framework* into *tmp_path* and return its root."""
    dest = tmp_path / framework
    result = InitScaffoldTool().execute(
        path=str(dest),
        name="my-app",
        org="acme",
        author="Dev",
        email="dev@example.com",
        framework=framework,
    )
    assert result.success, result.error
    return dest


@pytest.mark.integration
def test_scaffolded_node_project_passes_its_checks(tmp_path: Path) -> None:
    """A scaffolded node project is detected as node and scores 100."""
    dest = _scaffold(tmp_path, "node")
    engine = CheckEngine(dest)
    assert engine.framework is Framework.NODE
    result = engine.run()
    assert result.score == 100


@pytest.mark.integration
def test_scaffolded_svelte_project_passes_its_checks(tmp_path: Path) -> None:
    """A scaffolded svelte project runs node base + svelte delta and scores 100."""
    dest = _scaffold(tmp_path, "svelte")
    engine = CheckEngine(dest)
    assert engine.framework is Framework.SVELTE
    result = engine.run()
    assert result.score == 100
    # The svelte delta check ran on top of the node base checks.
    names = {c.name for c in result.checks}
    assert "config.svelte_config" in names
    assert "package_json.package_json_exists" in names
