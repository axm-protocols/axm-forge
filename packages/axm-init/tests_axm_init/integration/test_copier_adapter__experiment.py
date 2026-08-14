"""Integration: rendering the bundled experiment template via Copier.

Real I/O: every test renders the packaged ``experiment`` template into a
``tmp_path`` destination through the public :class:`CopierAdapter` surface.
The assertions stay inside this package (rendered tree, rendered manifest
keys, rendered git-ignore); the authoritative round-trip validation of the
manifest against the axm-lab model belongs to axm-lab's own suite.
"""

from __future__ import annotations

import json
import shutil
from fnmatch import fnmatch
from pathlib import Path

import pytest
import yaml

from axm_init.adapters.copier import CopierAdapter, CopierConfig
from axm_init.core.templates import TemplateType, get_template_path

pytestmark = pytest.mark.integration

DESCRIPTIVE_ANSWERS: dict[str, str] = {
    "experiment_id": "exp-0001-corpus-shape",
    "experiment_title": "Corpus shape descriptive pass",
    "research_question": "How is the corpus distributed across sources?",
    "experiment_kind": "descriptive",
    "reproduction_level": "tolerance",
}

EXPERIMENT_KINDS = frozenset({"hypothesis-testing", "descriptive", "exploratory"})
REPRODUCTION_LEVELS = frozenset({"exact", "tolerance", "attested"})

MANIFEST = "experiment.yaml"

GOLDEN_TREE = frozenset(
    {
        ".gitignore",
        "README.md",
        "analysis/ANALYSIS.md",
        "analysis/metrics.json",
        "experiment.yaml",
        "figures/FIGURES.md",
        "inputs/SOURCES.md",
        "outputs/.gitkeep",
        "scripts/.gitkeep",
    }
)

GOLDEN_DIRS = frozenset({"analysis", "figures", "inputs", "outputs", "scripts"})

NOISE_NAMES = frozenset({"__pycache__", ".mypy_cache", ".ruff_cache", ".DS_Store"})


def _render(
    destination: Path,
    *,
    template_path: Path | None = None,
    **overrides: str,
) -> Path:
    """Render the experiment template into *destination* and return it."""
    source = template_path or Path(get_template_path(TemplateType.EXPERIMENT))
    destination.mkdir(parents=True, exist_ok=True)
    result = CopierAdapter().copy(
        CopierConfig(
            template_path=source,
            destination=destination,
            data=dict(DESCRIPTIVE_ANSWERS) | overrides,
            defaults=True,
            overwrite=True,
        )
    )
    assert result.success, result.message
    return destination


def _relative_files(root: Path) -> set[str]:
    """Return every rendered file path, relative to *root*, POSIX style."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def _ignore_patterns(text: str) -> list[str]:
    """Return the active (non-blank, non-comment) git-ignore patterns."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _is_ignored(patterns: list[str], path: str) -> bool:
    """Whether *path* is matched by one of the git-ignore *patterns*."""
    literals = {path, f"{path}/", f"/{path}", f"/{path}/"}
    return any(
        pattern in literals or fnmatch(path, pattern.strip("/")) for pattern in patterns
    )


def test_descriptive_render_matches_golden_tree(tmp_path: Path) -> None:
    """AC2: the descriptive kind renders the canonical tree at the render root."""
    root = _render(tmp_path / "render")
    assert _relative_files(root) == set(GOLDEN_TREE)
    assert {p.name for p in root.iterdir() if p.is_dir()} == set(GOLDEN_DIRS)


def test_manifest_carries_every_answer(tmp_path: Path) -> None:
    """AC3: each Copier answer lands under its declared manifest key."""
    root = _render(tmp_path / "render")
    raw = (root / MANIFEST).read_text(encoding="utf-8")
    manifest = yaml.safe_load(raw)
    assert isinstance(manifest, dict), raw
    for key in DESCRIPTIVE_ANSWERS:
        assert key in manifest, f"missing manifest key: {key}"
        assert str(manifest[key]).strip(), f"empty manifest value: {key}"
    assert manifest["experiment_kind"] in EXPERIMENT_KINDS
    assert manifest["reproduction_level"] in REPRODUCTION_LEVELS
    assert DESCRIPTIVE_ANSWERS["experiment_title"] in raw
    assert DESCRIPTIVE_ANSWERS["research_question"] in raw
    assert "TODO" not in raw


def test_hypothesis_kind_adds_the_freeze(tmp_path: Path) -> None:
    """AC4: only the hypothesis-testing kind renders the freeze directory."""
    hypothesis = _render(tmp_path / "hypothesis", experiment_kind="hypothesis-testing")
    descriptive = _render(tmp_path / "descriptive", experiment_kind="descriptive")
    spec = hypothesis / "freeze" / "model_spec.json"
    assert spec.is_file(), sorted(_relative_files(hypothesis))
    assert isinstance(json.loads(spec.read_text(encoding="utf-8")), dict)
    assert _relative_files(hypothesis) == set(GOLDEN_TREE) | {"freeze/model_spec.json"}
    assert not (descriptive / "freeze").exists()


def test_gitignore_versions_evidence_and_excludes_caches(tmp_path: Path) -> None:
    """AC5: the rendered git-ignore keeps the evidence and drops the caches."""
    root = _render(tmp_path / "render")
    patterns = _ignore_patterns((root / ".gitignore").read_text(encoding="utf-8"))
    for evidence in (
        "freeze",
        MANIFEST,
        "experiment.lock.yaml",
        "analysis",
        "figures",
        "README.md",
    ):
        assert not _is_ignored(patterns, evidence), f"{evidence} must be versioned"
    for excluded in ("__pycache__", ".venv"):
        assert _is_ignored(patterns, excluded), f"{excluded} must be ignored"


def test_template_caches_never_reach_the_render(tmp_path: Path) -> None:
    """AC6: caches and macOS metadata inside the template never get rendered."""
    source = tmp_path / "template"
    shutil.copytree(Path(get_template_path(TemplateType.EXPERIMENT)), source)
    for noise in ("__pycache__", ".mypy_cache", ".ruff_cache"):
        (source / noise).mkdir(parents=True, exist_ok=True)
        (source / noise / "stale.txt").write_text("stale", encoding="utf-8")
    (source / ".DS_Store").write_text("junk", encoding="utf-8")
    root = _render(tmp_path / "render", template_path=source)
    polluted = sorted(p.name for p in root.rglob("*") if p.name in NOISE_NAMES)
    assert polluted == []
