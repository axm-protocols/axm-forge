"""Domain operations must never fall back to bundled business scaffolds."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from axm_init import scaffolding as api
from axm_init.core.learning_profile import declared_learning_domain
from axm_init.tools.scaffold import InitScaffoldTool


@pytest.mark.parametrize(
    "kind,package",
    [("learning", "axm-learning"), ("experiment", "axm-lab"), ("project", "axm-lab")],
)
def test_absent_domain_provider_refuses_public_render(
    monkeypatch, tmp_path, kind, package
):
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[]))
    adapter = Mock()
    monkeypatch.setattr(api, "CopierAdapter", adapter)
    target = tmp_path / "target"
    result = api.render_scaffold(kind, target, {})
    assert not result.success
    assert package in result.message
    assert "install" in result.message.lower()
    adapter.assert_not_called()
    assert not target.exists()


def test_learning_metadata_requires_provider_even_without_metadata(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[]))
    with pytest.raises(api.ProviderError, match="axm-learning"):
        declared_learning_domain(tmp_path)


def test_experiment_route_uses_modern_provider_at_destination(monkeypatch, tmp_path):
    template = tmp_path / "template"
    template.mkdir()
    (template / "copier.yml").write_text("{}\n")
    (template / "experiment.toml.jinja").write_text("schema_version = 2\n")
    provider = Mock(spec=["layers", "finalize"])
    provider.layers.return_value = (
        api.TemplateLayer(name="experiment", path=template, data={}),
    )
    monkeypatch.setattr(api, "load_provider", lambda kind: provider)
    target = tmp_path / "modern"
    result = InitScaffoldTool().execute(
        path=str(target),
        kind="experiment",
        name="baseline",
        org="test",
        author="Test",
        email="test@example.com",
    )
    assert not result.success
    assert "experiment_scaffold" in result.error
    assert "axm-lab" in result.error
    assert not target.exists()
    provider.layers.assert_not_called()


def test_no_bundled_domain_templates():
    from axm_init.core.templates import TEMPLATES_PKG

    for name in ("experiment", "learning-project", "learning-profile"):
        assert not Path(str(TEMPLATES_PKG / name)).exists()


def test_experiment_rules_are_not_bundled():
    from axm_init.core.checker import ALL_CHECKS

    assert "experiment" not in ALL_CHECKS


def test_investigation_absence_has_install_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[]))
    result = api.render_scaffold("investigation", tmp_path / "target", {})
    assert not result.success
    assert "install axm-lab" in result.message


def test_experiment_check_directs_to_lab_without_scoring(tmp_path):
    from axm_init.tools.check import InitCheckTool

    (tmp_path / "manifest.yaml").write_text("contract_version: 2.0.0\nid: demo\n")
    result = InitCheckTool().execute(path=str(tmp_path))
    assert not result.success
    assert "axm-lab" in result.error
    assert "experiment_check" in result.error


def test_paper_scaffold_routes_to_lab(tmp_path):
    result = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="paper",
        name="paper",
        org="test",
        author="Test",
        email="test@example.com",
    )
    assert not result.success
    assert "paper_scaffold" in result.error
    assert not list(tmp_path.iterdir())
