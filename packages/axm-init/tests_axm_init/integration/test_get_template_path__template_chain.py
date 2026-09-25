"""Integration contracts for ordered template-chain resolution."""

from __future__ import annotations

import pytest

from axm_init.core import templates
from axm_init.scaffolding import ScaffoldRequest
from tests_axm_init._learning_provider import FakeLearningProvider


@pytest.mark.integration
@pytest.mark.parametrize(("member", "existing"), [(False, False), (True, True)])
def test_learning_chain_is_owned_by_the_installed_provider(
    fake_learning_provider: FakeLearningProvider, member: bool, existing: bool
) -> None:
    """AC1: learning layers come from the provider, given the full request."""
    layers = templates.template_chain(
        templates.TemplateType.LEARNING,
        framework=None,
        member=member,
        existing=existing,
    )

    assert fake_learning_provider.calls == [
        ("layers", (ScaffoldRequest("learning", None, member, existing),))
    ]
    assert layers[-1].name == "learning"


@pytest.mark.integration
def test_non_learning_type_keeps_single_resolved_layer() -> None:
    """AC4: a non-learning type remains one get_template_path layer."""
    layers = templates.template_chain(
        templates.TemplateType.STANDALONE,
        framework=None,
        member=False,
    )

    assert len(layers) == 1
    assert layers[0].path == templates.get_template_path(
        templates.TemplateType.STANDALONE,
        None,
    )
