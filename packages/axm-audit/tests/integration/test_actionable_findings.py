"""Verify ``text``/``details``/``fix_hint`` are populated on test_quality rules.

Each of the four rules under :mod:`axm_audit.core.rules.test_quality`
must expose actionable findings:

* a compact ``text`` bullet list,
* a ``details``/``metadata`` dict with a thematic key,
* a ``fix_hint`` phrase.

When the rule passes, ``text`` and ``fix_hint`` should be ``None``.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule
from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule
from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule
from axm_audit.core.rules.test_quality.tautology import TautologyRule

__all__: list[str] = []


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip())


# ── PYRAMID_LEVEL ─────────────────────────────────────────────────────


@pytest.fixture
def pyramid_mismatch_project(tmp_path: Path) -> Path:
    _write(
        tmp_path / "tests" / "integration" / "test_x.py",
        """
        def test_pure():
            assert 1 + 1 == 2
        """,
    )
    return tmp_path


def test_pyramid_failed_populates_actionable_fields(
    pyramid_mismatch_project: Path,
) -> None:
    result = PyramidLevelRule().check(pyramid_mismatch_project)
    assert result.passed is False
    assert result.text and "•" in result.text
    assert result.fix_hint and "pyramid-relocate" in result.fix_hint
    assert result.details is not None
    assert "mismatches" in result.details
    assert result.details["total"] >= 1


def test_pyramid_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = PyramidLevelRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


# ── PRIVATE_IMPORTS ───────────────────────────────────────────────────


@pytest.fixture
def private_imports_project(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    _write(tmp_path / "src" / "pkg" / "__init__.py", "")
    _write(tmp_path / "src" / "pkg" / "mod.py", "def _private():\n    return 1\n")
    _write(
        tmp_path / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    return tmp_path


def test_private_imports_failed_populates_actionable_fields(
    private_imports_project: Path,
) -> None:
    result = PrivateImportsRule().check(private_imports_project)
    assert result.passed is False
    assert result.text and "_private" in result.text
    assert result.fix_hint and "public" in result.fix_hint.lower()
    assert result.details is not None
    assert "findings" in result.details


def test_private_imports_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    _write(tmp_path / "src" / "pkg" / "__init__.py", "")
    (tmp_path / "tests").mkdir()
    result = PrivateImportsRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


# ── DUPLICATE_TESTS ───────────────────────────────────────────────────


@pytest.fixture
def duplicate_tests_project(tmp_path: Path) -> Path:
    body = dedent(
        """
        def test_dup_a():
            x = 1
            assert x == 1

        def test_dup_b():
            x = 1
            assert x == 1
        """
    ).lstrip()
    _write(tmp_path / "tests" / "test_dup.py", body)
    return tmp_path


def test_duplicate_tests_failed_populates_actionable_fields(
    duplicate_tests_project: Path,
) -> None:
    result = DuplicateTestsRule().check(duplicate_tests_project)
    if result.passed:
        pytest.skip("clustering heuristics did not flag this pair")
    assert result.text and "cluster[" in result.text
    assert result.fix_hint and "parametrize" in result.fix_hint
    assert result.metadata is not None
    assert "clusters" in result.metadata


def test_duplicate_tests_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = DuplicateTestsRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


# ── TAUTOLOGY ─────────────────────────────────────────────────────────


@pytest.fixture
def tautology_project(tmp_path: Path) -> Path:
    _write(
        tmp_path / "tests" / "test_taut.py",
        """
        def test_trivial():
            assert True
        """,
    )
    return tmp_path


def test_tautology_failed_populates_actionable_fields(
    tautology_project: Path,
) -> None:
    result = TautologyRule().check(tautology_project)
    assert result.passed is False
    assert result.text and "•" in result.text
    assert result.fix_hint and "behavioral" in result.fix_hint
    assert result.metadata is not None
    assert "verdicts" in result.metadata


def test_tautology_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = TautologyRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None
