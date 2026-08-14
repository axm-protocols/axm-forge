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

# Spellings retired by the manifest rename: neither the legacy answer name nor
# the hyphenated value may survive in any shipped template entry name.
LEGACY_TEMPLATE_SPELLINGS = ("experiment_kind", "hypothesis-testing")

EXPERIMENT_TYPES = frozenset({"hypothesis_testing", "descriptive", "exploratory"})
REPRO_LEVELS = frozenset({"exact", "tolerance", "attested"})

# The figure declaration contract: the scaffolded skeleton must name these four
# keys (commented example entry) while declaring no figure of its own.
FIGURE_KEYS = ("id", "caption", "script", "reads")

# The minimal answer set: only the questions carrying no default. The kind and
# the reproduction level are deliberately left to the template's own defaults,
# so a default render is what the contract assertions below observe.
MINIMAL_ANSWERS: dict[str, str] = {
    "experiment_id": "exp-0001-corpus-shape",
    "experiment_title": "Corpus shape descriptive pass",
    "research_question": "How is the corpus distributed across sources?",
}


def _render(destination: Path, extra: dict[str, str] | None = None) -> Path:
    """Render the experiment template with its defaults into *destination*."""
    source = Path(get_template_path(TemplateType.EXPERIMENT))
    destination.mkdir(parents=True, exist_ok=True)
    answers = dict(MINIMAL_ANSWERS)
    answers.update(extra or {})
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=source,
            destination=destination,
            data=answers,
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


# The falsifier sub-contract, transcribed by hand from the experiment contract
# 1.0.0 (no axm-lab import: that package is unresolvable from axm-forge CI).
# ``falsifier`` is required and non-null iff the type is hypothesis_testing,
# absent or null otherwise, and when present it is the mapping
# ``{spec: "<non-empty str>", conditions: []}`` with extra keys forbidden.
FALSIFIER_KEYS = frozenset({"spec", "conditions"})


def _assert_falsifier_contract(document: dict[str, Any], exp_type: str) -> None:
    """Assert the rendered manifest honours the falsifier sub-contract."""
    falsifier = document.get("falsifier")
    assert (falsifier is not None) is (exp_type == "hypothesis_testing"), document
    if falsifier is None:
        return
    assert isinstance(falsifier, dict), falsifier
    assert set(falsifier.keys()) == set(FALSIFIER_KEYS), sorted(falsifier)
    spec = falsifier["spec"]
    assert isinstance(spec, str), spec
    assert spec.strip() != "", repr(spec)
    assert falsifier["conditions"] == [], falsifier["conditions"]


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


def test_hypothesis_testing_render_creates_the_freeze_directory(tmp_path: Path) -> None:
    """AC1: answering type=hypothesis_testing renders the freeze/ directory."""
    root = _render(tmp_path / "render", {"type": "hypothesis_testing"})
    assert (root / "freeze").is_dir(), _relative_files(root)


def test_shipped_template_tree_has_no_legacy_answer_spelling() -> None:
    """AC2: no entry name in the shipped template carries the legacy spelling."""
    template_root = Path(get_template_path(TemplateType.EXPERIMENT))
    assert template_root.is_dir(), str(template_root)
    offenders = sorted(
        entry.relative_to(template_root).as_posix()
        for entry in template_root.rglob("*")
        if any(spelling in entry.name for spelling in LEGACY_TEMPLATE_SPELLINGS)
    )
    assert offenders == []


def test_render_writes_no_metrics_json_anywhere(tmp_path: Path) -> None:
    """AC1: a rendered experiment holds no metrics.json in its whole tree."""
    root = _render(tmp_path / "render")
    offenders = sorted(
        path.relative_to(root).as_posix() for path in root.rglob("metrics.json")
    )
    assert offenders == [], _relative_files(root)


def test_render_writes_the_analysis_note_and_no_metrics_file(tmp_path: Path) -> None:
    """AC3: analysis/analysis.md is rendered and analysis/ holds no metrics file."""
    root = _render(tmp_path / "render")
    analysis = root / "analysis"
    assert analysis.is_dir(), _relative_files(root)
    present = sorted(entry.name for entry in analysis.rglob("*") if entry.is_file())
    assert (analysis / "analysis.md").is_file(), present
    metrics = [name for name in present if name.startswith("metrics.")]
    assert metrics == []


def test_render_writes_the_figures_declaration_not_the_prose_note(
    tmp_path: Path,
) -> None:
    """AC1: the render writes figures/figures.yaml and never figures/FIGURES.md."""
    root = _render(tmp_path / "render")
    rendered = _relative_files(root)
    assert (root / "figures" / "figures.yaml").is_file(), rendered
    leftovers = [path for path in rendered if path.endswith("FIGURES.md")]
    assert leftovers == []


def test_rendered_figures_declaration_is_an_empty_yaml_skeleton(
    tmp_path: Path,
) -> None:
    """AC2: figures.yaml parses empty and its text names the four contract keys."""
    root = _render(tmp_path / "render")
    raw = (root / "figures" / "figures.yaml").read_text(encoding="utf-8")
    document = yaml.safe_load(raw)
    assert document is None or document == [], document
    missing = [key for key in FIGURE_KEYS if key not in raw]
    assert missing == [], raw


@pytest.mark.parametrize(
    "exp_type", ["hypothesis_testing", "descriptive", "exploratory"]
)
def test_manifest_falsifier_honours_the_contract_for_every_type(
    tmp_path: Path, exp_type: str
) -> None:
    """AC3: the structural validator passes for the three experiment types."""
    root = _render(
        tmp_path / "render",
        {"type": exp_type, "repro_level": "exact"},
    )
    document = _manifest(root)
    assert document["type"] == exp_type
    _assert_falsifier_contract(document, exp_type)
    if exp_type != "hypothesis_testing":
        assert document.get("falsifier") is None, document["falsifier"]


def test_hypothesis_testing_manifest_renders_a_falsifier_mapping(
    tmp_path: Path,
) -> None:
    """AC1: falsifier is a mapping carrying a non-empty string spec."""
    root = _render(
        tmp_path / "render",
        {"type": "hypothesis_testing", "repro_level": "exact"},
    )
    assert (root / MANIFEST).is_file(), _relative_files(root)
    document = _manifest(root)
    falsifier = document["falsifier"]
    assert isinstance(falsifier, dict), falsifier
    spec = falsifier["spec"]
    assert isinstance(spec, str), spec
    assert spec.strip() != "", repr(spec)


def test_hypothesis_testing_falsifier_keys_are_spec_and_conditions(
    tmp_path: Path,
) -> None:
    """AC2: falsifier keys equal {spec, conditions} and conditions is []."""
    root = _render(
        tmp_path / "render",
        {"type": "hypothesis_testing", "repro_level": "exact"},
    )
    falsifier = _manifest(root)["falsifier"]
    assert isinstance(falsifier, dict), falsifier
    assert set(falsifier.keys()) == {"spec", "conditions"}, sorted(falsifier)
    assert falsifier["conditions"] == [], falsifier["conditions"]
