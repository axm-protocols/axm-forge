"""Public optional provider discovery and real Copier rendering contracts."""

from importlib.metadata import EntryPoint
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from axm_init import scaffolding as api


def _provider(monkeypatch, tmp_path: Path, *, name: str = "learning"):
    template = tmp_path / "template"
    template.mkdir()
    (template / "copier.yml").write_text("title: Example\n")
    (template / "domain.txt.jinja").write_text("{{ title }}:{{ domain }}\n")
    layer = api.TemplateLayer(name=name, path=template, data={"domain": name})
    provider = SimpleNamespace(layers=Mock(return_value=(layer,)))
    entry = Mock(spec=EntryPoint)
    entry.name = name
    entry.load.return_value = Mock(return_value=provider)
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[entry]))
    return provider, entry


def test_missing_provider_is_explicit_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[]))
    assert api.load_provider("missing") is None
    target = tmp_path / "target"
    result = api.render_scaffold("missing", target, {})
    assert not result.success
    assert "provider" in result.message.lower()
    assert not target.exists()


def test_discovery_loads_only_requested_provider(monkeypatch, tmp_path):
    provider, entry = _provider(monkeypatch, tmp_path)
    assert api.load_provider("learning") is provider
    api.entry_points.assert_called_once_with(
        group="axm.scaffold_providers", name="learning"
    )
    entry.load.assert_called_once_with()


def test_duplicate_provider_fails_before_loading(monkeypatch, tmp_path):
    _, entry = _provider(monkeypatch, tmp_path)
    monkeypatch.setattr(api, "entry_points", Mock(return_value=[entry, entry]))
    with pytest.raises(api.ProviderError, match="Duplicate"):
        api.load_provider("learning")
    entry.load.assert_not_called()


def test_invalid_provider_fails_with_actionable_error(monkeypatch, tmp_path):
    _, entry = _provider(monkeypatch, tmp_path)
    entry.load.return_value = lambda: object()
    with pytest.raises(api.ProviderError, match="layers"):
        api.load_provider("learning")


def test_provider_renders_with_existing_layer_engine(monkeypatch, tmp_path):
    provider, _ = _provider(monkeypatch, tmp_path)
    target = tmp_path / "target"
    result = api.render_scaffold("learning", target, {"title": "Rendered"})
    assert result.success, result.message
    assert (target / "domain.txt").read_text() == "Rendered:learning\n"
    assert (target / ".copier-answers.learning.yml").is_file()
    provider.layers.assert_called_once_with(api.ScaffoldRequest(kind="learning"))


@pytest.mark.parametrize("existing", ["directory", "file", "symlink"])
def test_render_refuses_existing_content(monkeypatch, tmp_path, existing):
    provider, _ = _provider(monkeypatch, tmp_path)
    target = tmp_path / "target"
    if existing == "directory":
        target.mkdir()
        protected = target / "domain.txt"
    elif existing == "symlink":
        protected = tmp_path / "protected"
        protected.mkdir()
        target.symlink_to(protected, target_is_directory=True)
        protected = protected / "domain.txt"
    else:
        protected = target
    protected.write_bytes(b"user-owned\x00content")
    result = api.render_scaffold("learning", target, {})
    assert not result.success
    assert protected.read_bytes() == b"user-owned\x00content"
    provider.layers.assert_not_called()


def test_duplicate_layer_names_are_rejected_before_render(monkeypatch, tmp_path):
    provider, _ = _provider(monkeypatch, tmp_path)
    layer = provider.layers.return_value[0]
    provider.layers.return_value = (layer, layer)
    target = tmp_path / "target"
    result = api.render_scaffold("learning", target, {})
    assert not result.success
    assert "layer" in result.message.lower()
    assert not target.exists()


@pytest.mark.parametrize("kind", ["learning", "experiment"])
def test_init_routes_delegate_to_installed_provider(monkeypatch, tmp_path, kind):
    from axm_init.tools.scaffold import InitScaffoldTool

    provider, _ = _provider(monkeypatch, tmp_path, name=kind)
    target = tmp_path / "target"
    target.mkdir()
    if kind == "experiment":
        provider.legacy_experiment_layers = Mock(
            return_value=provider.layers.return_value
        )
        (target / "paper").mkdir()
        (target / "experiments").mkdir()
        (target / "PLAN.md").write_text("Plan")
    result = InitScaffoldTool().execute(
        path=str(target),
        name="baseline",
        kind=kind,
        org="test",
        author="Test",
        email="test@example.com",
    )
    assert result.success, result.error
    if kind == "experiment":
        provider.legacy_experiment_layers.assert_called_once_with()
        provider.layers.assert_not_called()
    else:
        provider.layers.assert_called_once_with(api.ScaffoldRequest(kind=kind))
    rendered = target if kind == "learning" else target / "experiments/01-baseline"
    assert (rendered / "domain.txt").read_text() == f"Example:{kind}\n"


def test_legacy_learning_metadata_delegates(monkeypatch, tmp_path):
    from axm_init.core.learning_profile import (
        declared_learning_domain,
        merge_learning_metadata,
        register_learning_profile,
    )

    provider, _ = _provider(monkeypatch, tmp_path)
    provider.declared_learning_domain = Mock(return_value="forecast")
    provider.merge_learning_metadata = Mock(return_value="provider metadata")
    provider.register_learning_profile = Mock()
    assert declared_learning_domain(tmp_path, "forecast") == "forecast"
    assert (
        merge_learning_metadata("original", "forecast", "sample") == "provider metadata"
    )
    register_learning_profile(tmp_path, "forecast", "sample")
    provider.register_learning_profile.assert_called_once_with(
        tmp_path, "forecast", "sample"
    )


def test_legacy_learning_check_delegates_before_legacy_toml_guard(
    monkeypatch, tmp_path
):
    from axm_init.checks.learning import check_learning_profile
    from axm_init.rules import CheckResult

    provider, _ = _provider(monkeypatch, tmp_path)
    finding = CheckResult(
        name="learning.profile",
        category="learning",
        passed=True,
        weight=0,
        message="Provider finding",
        details=[],
        fix="",
    )
    provider.check_learning_profile = Mock(return_value=finding)
    assert check_learning_profile(tmp_path) is finding


def test_legacy_experiment_does_not_use_modern_provider_answers(monkeypatch, tmp_path):
    from axm_init.tools.scaffold import InitScaffoldTool

    provider, _ = _provider(monkeypatch, tmp_path, name="experiment")
    target = tmp_path / "paper-root"
    target.mkdir()
    (target / "paper").mkdir()
    (target / "experiments").mkdir()
    (target / "PLAN.md").write_text("Plan")
    result = InitScaffoldTool().execute(
        path=str(target),
        name="baseline",
        kind="experiment",
        org="test",
        author="Test",
        email="test@example.com",
    )
    assert result.success, result.error
    provider.layers.assert_not_called()
    assert (target / "experiments/01-baseline/manifest.yaml").is_file()


@pytest.mark.parametrize("member", [False, True])
def test_public_render_finalizes_successful_provider(monkeypatch, tmp_path, member):
    provider, _ = _provider(monkeypatch, tmp_path)
    target = tmp_path / "target"
    data = {"title": "Rendered"}

    def finalize(request, destination, answers):
        assert (destination / "domain.txt").is_file()
        assert request == api.ScaffoldRequest("learning", member=member)
        assert answers == data
        (destination / "metadata.txt").write_text("complete")

    provider.finalize = Mock(side_effect=finalize)
    result = api.render_scaffold("learning", target, data, member=member)
    assert result.success, result.message
    assert (target / "metadata.txt").read_text() == "complete"
    provider.finalize.assert_called_once()


@pytest.mark.parametrize("error", [ValueError, RuntimeError])
def test_public_render_reports_finalization_failure(monkeypatch, tmp_path, error):
    provider, _ = _provider(monkeypatch, tmp_path)
    provider.finalize = Mock(side_effect=error("Invalid domain metadata"))
    result = api.render_scaffold("learning", tmp_path / "target", {})
    assert not result.success
    assert "Invalid domain metadata" in result.message


def test_failed_render_does_not_finalize(monkeypatch, tmp_path):
    provider, _ = _provider(monkeypatch, tmp_path)
    provider.finalize = Mock()
    monkeypatch.setattr(
        api.CopierAdapter,
        "apply_chain",
        Mock(
            return_value=api.ScaffoldResult(
                success=False, path=str(tmp_path), message="Rendering failed"
            )
        ),
    )
    result = api.render_scaffold("learning", tmp_path / "target", {})
    assert not result.success
    provider.finalize.assert_not_called()


def test_generator_layers_fail_before_render(monkeypatch, tmp_path):
    provider, _ = _provider(monkeypatch, tmp_path)
    provider.layers.return_value = iter(provider.layers.return_value)
    result = api.render_scaffold("learning", tmp_path / "target", {})
    assert not result.success
    assert not (tmp_path / "target").exists()


def test_provider_layer_failure_is_structured(monkeypatch, tmp_path):
    provider, _ = _provider(monkeypatch, tmp_path)
    provider.layers.side_effect = RuntimeError("Provider configuration unavailable")
    result = api.render_scaffold("learning", tmp_path / "target", {})
    assert not result.success
    assert "Provider configuration unavailable" in result.message
    assert not (tmp_path / "target").exists()
