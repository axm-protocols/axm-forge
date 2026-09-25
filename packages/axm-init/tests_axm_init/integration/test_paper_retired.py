"""Init must not retain a bundled paper or paper rulebook."""

import pytest

from axm_init.core.checker import ALL_CHECKS, CheckEngine
from axm_init.core.templates import TemplateType, get_template_path


def test_no_paper_fallback():
    with pytest.raises(ValueError, match="axm-lab"):
        get_template_path(TemplateType.PAPER)


def test_obsolete_entrypoint_routes_before_identity_or_network(tmp_path):
    from axm_init.tools.scaffold import InitScaffoldTool

    result = InitScaffoldTool().execute(
        path=str(tmp_path), kind="paper", check_pypi=True
    )
    assert not result.success
    assert "paper_scaffold" in result.error
    assert not list(tmp_path.iterdir())


def test_paper_checks_route_to_lab(tmp_path):
    assert "paper" not in ALL_CHECKS
    with pytest.raises(ValueError, match="paper_check"):
        CheckEngine(tmp_path, category="paper")
