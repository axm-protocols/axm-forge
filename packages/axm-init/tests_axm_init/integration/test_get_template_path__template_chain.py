"""Integration contracts for ordered template-chain resolution."""

from __future__ import annotations

import pytest

from axm_init.core import templates


@pytest.mark.integration
def test_learning_standalone_resolves_base_then_learning() -> None:
    """AC1: standalone learning composes base then learning templates."""
    layers = templates.template_chain(
        templates.TemplateType.LEARNING,
        framework=None,
        member=False,
    )

    assert len(layers) == 2
    assert [layer.path.name for layer in layers] == [
        "python-project",
        "learning-project",
    ]


@pytest.mark.integration
def test_learning_standalone_sets_overlay_only_on_learning_layer() -> None:
    """AC2: only the learning layer carries overlay mode."""
    base_layer, learning_layer = templates.template_chain(
        templates.TemplateType.LEARNING,
        framework=None,
        member=False,
    )

    assert "learning_mode" not in base_layer.data
    assert learning_layer.data["learning_mode"] == "overlay"


@pytest.mark.integration
def test_learning_member_is_standalone_learning_layer() -> None:
    """AC3: a workspace member uses one standalone learning layer."""
    layers = templates.template_chain(
        templates.TemplateType.LEARNING,
        framework=None,
        member=True,
    )

    assert len(layers) == 1
    assert layers[0].path.name == "learning-project"
    assert layers[0].data["learning_mode"] == "standalone"


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
