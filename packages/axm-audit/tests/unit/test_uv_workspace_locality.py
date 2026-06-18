"""Unit tests for :class:`UvWorkspaceLocalityRule`.

The rule must distinguish two situations for an offending site:

* ``axm-ingot`` is importable from the audited project -> BLOCKING
  (``passed=False``, score penalised) as before.
* ``axm-ingot`` is NOT importable -> WARN-ONLY (``passed=True``, score
  not penalised, site still listed in ``details`` with an actionable note).

These tests mock the importability decision in-memory (no real I/O): the
source scan is driven through a fake ``src/`` tree built in ``tmp_path`` but
the importability of ``axm-ingot`` is forced via ``find_spec`` and the
pyproject heuristics so each branch is exercised deterministically.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from axm_audit.core.rules.architecture.uv_workspace_locality import (
    UvWorkspaceLocalityRule,
)

_OFFENDING = (
    "import tomllib\n\n\n"
    "def parse(p):\n"
    "    data = tomllib.loads(p.read_text())\n"
    '    return data["tool"]["uv"]["workspace"]\n'
)


def _make_project(root: Path, *, offending: bool) -> Path:
    """Build a minimal package layout under *root* and return it."""
    src = root / "src" / "somepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    body = _OFFENDING if offending else "def clean():\n    return 1\n"
    (src / "mod.py").write_text(body)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "somepkg"\nversion = "0.1.0"\n'
    )
    return root


@pytest.fixture
def rule() -> UvWorkspaceLocalityRule:
    """Return a fresh rule instance."""
    return UvWorkspaceLocalityRule()


def test_blocking_when_ingot_importable(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: offending site + ingot importable -> blocking (passed=False)."""
    project = _make_project(tmp_path, offending=True)
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "axm_ingot" else None,
    )

    result = rule.check(project)

    assert result.passed is False
    assert result.score < 100
    assert result.details["sites"]


def test_warn_only_when_ingot_absent(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2, AC3: offending site + ingot NOT importable -> warn-only.

    The site is still surfaced in ``details`` and the message carries an
    actionable note that ``axm-ingot`` is not importable here.
    """
    project = _make_project(tmp_path, offending=True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a, **k: None)

    result = rule.check(project)

    assert result.passed is True
    assert result.score == 100
    assert result.details["sites"]
    note = (
        result.message + str(result.text or "") + str(result.fix_hint or "")
    ).lower()
    assert "importable" in note


def test_clean_project_passes(
    rule: UvWorkspaceLocalityRule,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4: no offending site -> passed with zero finding."""
    project = _make_project(tmp_path, offending=False)
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name, *a, **k: object() if name == "axm_ingot" else None,
    )

    result = rule.check(project)

    assert result.passed is True
    assert result.score == 100
    assert result.details["sites"] == []
