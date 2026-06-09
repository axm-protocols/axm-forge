"""Integration: a freshly scaffolded project scores 100 on wheel_doc_shipping.

AC1 — scaffold a real project via Copier from the ``python-project``
(standalone) template, then run the full ``CheckEngine``. A fresh
scaffold must score exactly 100 with no ``pyproject.wheel_doc_shipping``
failure (the scaffold ships ``docs/index.md`` force-included in its wheel).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.checker import CheckEngine
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

_DATA = {
    "package_name": "scaffold-check-demo",
    "description": "A modern Python package",
    "org": "DemoOrg",
    "license": "MIT",
    "license_holder": "DemoOrg",
    "author_name": "Demo Author",
    "author_email": "demo@example.com",
}


@pytest.fixture(scope="module")
def scaffolded_standalone(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Scaffold the standalone (python-project) template once via real Copier."""
    target = tmp_path_factory.mktemp("scaffold_check") / "demo-pkg"
    config = CopierConfig(
        template_path=get_template_path(TemplateType.STANDALONE),
        destination=target,
        data=_DATA,
        trust_template=True,
    )
    CopierAdapter().copy(config)
    return target


def test_scaffolded_project_scores_100(scaffolded_standalone: Path) -> None:
    """AC1: fresh scaffold scores 100 with no wheel_doc_shipping failure."""
    result = CheckEngine(scaffolded_standalone).run()

    failed_names = {c.name for c in result.failures}
    assert "pyproject.wheel_doc_shipping" not in failed_names, result.failures
    assert result.score == 100, sorted(failed_names)
