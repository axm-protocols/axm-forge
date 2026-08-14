"""Integration: rendering the bundled experiment template via Copier.

Real I/O: every test renders the packaged ``experiment`` template into a
``tmp_path`` destination through the public :class:`CopierAdapter` surface.
The assertions stay inside this package (rendered contract file, rendered
manifest keys and values); the authoritative round-trip validation of the
manifest against the axm-lab model belongs to axm-lab's own suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

MANIFEST = "manifest.yaml"
LEGACY_MANIFEST = "experiment.yaml"

CONTRACT_KEYS = frozenset(
    {
        "contract_version",
        "id",
        "title",
        "question",
        "type",
        "repro_level",
        "falsifier",
        "inputs",
        "steps",
        "bounds",
    }
)

REQUIRED_KEYS = frozenset(
    {"contract_version", "id", "title", "question", "type", "repro_level"}
)

LEGACY_KEYS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "experiment_title",
        "research_question",
        "experiment_kind",
        "reproduction_level",
        "paths",
    }
)

EXPERIMENT_TYPES = frozenset({"hypothesis_testing", "descriptive", "exploratory"})
REPRO_LEVELS = frozenset({"exact", "tolerance", "attested"})

# The minimal answer set: only the questions carrying no default. The kind and
# the reproduction level are deliberately left to the template's own defaults,
# so a default render is what the contract assertions below observe.
MINIMAL_ANSWERS: dict[str, str] = {
    "experiment_id": "exp-0001-corpus-shape",
    "experiment_title": "Corpus shape descriptive pass",
    "research_question": "How is the corpus distributed across sources?",
}


def _render(destination: Path) -> Path:
    """Render the experiment template with its defaults into *destination*."""
    source = Path(get_template_path(TemplateType.EXPERIMENT))
    destination.mkdir(parents=True, exist_ok=True)
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=source,
            destination=destination,
            data=dict(MINIMAL_ANSWERS),
            defaults=True,
            overwrite=True,
        )
    )
    assert result.success, result.message
    return destination


def _relative_files(root: Path) -> list[str]:
    """Return every rendered file path, relative to *root*, POSIX style."""
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


def _manifest(root: Path) -> dict[str, Any]:
    """Return the parsed contract manifest rendered at the experiment root."""
    raw = (root / MANIFEST).read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    assert isinstance(document, dict), raw
    return document


def test_render_writes_the_contract_manifest_only(tmp_path: Path) -> None:
    """AC1: the render writes manifest.yaml and no legacy experiment.yaml."""
    root = _render(tmp_path / "render")
    rendered = _relative_files(root)
    assert (root / MANIFEST).is_file(), rendered
    leftovers = [path for path in rendered if path.endswith(LEGACY_MANIFEST)]
    assert leftovers == []


def test_manifest_keys_match_the_contract_key_set(tmp_path: Path) -> None:
    """AC2: top-level keys are contract keys, required ones present, no legacy."""
    document = _manifest(_render(tmp_path / "render"))
    keys = set(document)
    assert keys <= set(CONTRACT_KEYS), sorted(keys - set(CONTRACT_KEYS))
    assert set(REQUIRED_KEYS) <= keys, sorted(set(REQUIRED_KEYS) - keys)
    assert keys.isdisjoint(LEGACY_KEYS), sorted(keys & set(LEGACY_KEYS))


def test_manifest_values_use_the_canonical_vocabularies(tmp_path: Path) -> None:
    """AC3: contract_version is the string 1.0.0, type/repro_level are canonical."""
    document = _manifest(_render(tmp_path / "render"))
    assert isinstance(document["contract_version"], str)
    assert document["contract_version"] == "1.0.0"
    assert document["type"] in EXPERIMENT_TYPES
    assert document["repro_level"] in REPRO_LEVELS
