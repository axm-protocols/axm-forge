"""Integration tests for ordered Copier template layers."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.adapters.copier import CopierAdapter
from axm_init.core.templates import TemplateLayer


def _write_template(
    root: Path,
    *,
    filename: str,
    rendered: str,
    skip_if_exists: bool = False,
) -> None:
    root.mkdir()
    config = "_skip_if_exists:\n  - protected.txt\n" if skip_if_exists else ""
    (root / "copier.yml").write_text(config)
    (root / f"{filename}.jinja").write_text(rendered)


def _two_layers(
    tmp_path: Path, *, protect_overlay: bool = False
) -> list[TemplateLayer]:
    base = tmp_path / "base-template"
    overlay = tmp_path / "overlay-template"
    _write_template(
        base,
        filename="base.txt",
        rendered="{{ shared }}:{{ layer_value }}\n",
    )
    _write_template(
        overlay,
        filename="protected.txt",
        rendered="{{ shared }}:{{ layer_value }}\n",
        skip_if_exists=protect_overlay,
    )
    return [
        TemplateLayer(name="base", path=base, data={"layer_value": "base"}),
        TemplateLayer(name="overlay", path=overlay, data={"layer_value": "overlay"}),
    ]


@pytest.mark.integration
def test_apply_chain_renders_both_layers_in_one_destination(tmp_path: Path) -> None:
    """AC1: both ordered layers render their own file in one destination."""
    destination = tmp_path / "project"

    result = CopierAdapter().apply_chain(
        _two_layers(tmp_path), destination, {"shared": "caller"}
    )

    assert result.success, result.message
    assert (destination / "base.txt").read_text() == "caller:base\n"
    assert (destination / "protected.txt").read_text() == "caller:overlay\n"


@pytest.mark.integration
def test_apply_chain_keeps_one_answers_file_per_layer(tmp_path: Path) -> None:
    """AC2: each layer owns an answers file retaining its source template."""
    destination = tmp_path / "project"
    layers = _two_layers(tmp_path)

    result = CopierAdapter().apply_chain(layers, destination, {"shared": "caller"})

    assert result.success, result.message
    base_answers = destination / ".copier-answers.base.yml"
    overlay_answers = destination / ".copier-answers.overlay.yml"
    assert base_answers.is_file()
    assert overlay_answers.is_file()
    assert str(layers[0].path) in base_answers.read_text()


@pytest.mark.integration
def test_apply_chain_reapply_preserves_skipped_and_regenerates_owned_file(
    tmp_path: Path,
) -> None:
    """AC3: reapply preserves layer-two skips and regenerates layer-one files."""
    destination = tmp_path / "project"
    layers = _two_layers(tmp_path, protect_overlay=True)
    adapter = CopierAdapter()
    first = adapter.apply_chain(layers, destination, {"shared": "caller"})
    assert first.success, first.message
    protected = destination / "protected.txt"
    owned = destination / "base.txt"
    protected_bytes = b"user-owned\x00bytes\n"
    protected.write_bytes(protected_bytes)
    owned.write_text("manual edit\n")

    second = adapter.apply_chain(layers, destination, {"shared": "caller"})

    assert second.success, second.message
    assert protected.read_bytes() == protected_bytes
    assert owned.read_text() == "caller:base\n"
