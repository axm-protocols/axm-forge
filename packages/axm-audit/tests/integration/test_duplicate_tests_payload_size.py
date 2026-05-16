"""Integration tests for duplicate_tests cluster payload size and shape (axm-1728)."""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule

pytestmark = pytest.mark.integration


def _write_duplicate_pair(tests_dir: Path) -> None:
    """Write two byte-identical tests into a temp tests/ directory."""
    tests_dir.mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent(
        """\
        def test_alpha():
            result = compute(1, 2)
            assert result == 3


        def test_beta():
            result = compute(1, 2)
            assert result == 3
        """
    )
    (tests_dir / "test_dupes.py").write_text(body, encoding="utf-8")


def _make_tmp_project(root: Path) -> Path:
    """Lay out a minimal project with one duplicate-test pair under tests/."""
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    _write_duplicate_pair(root / "tests")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    return root


def test_score_matches_pair_count_from_members(tmp_path: Path) -> None:
    """AC4: score from `members` matches pre-change behavior on 1-pair input."""
    project = _make_tmp_project(tmp_path)
    result = DuplicateTestsRule().check(project)
    assert result.score == 95
    assert re.search(r"1 cluster\(s\), 1 clustered pair\(s\)", result.message)


def test_self_audit_payload_under_size_threshold() -> None:
    """AC5: self-audit cluster payload is < 65 000 chars after the dedup."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    payload = json.dumps(result.metadata["clusters"])
    assert len(payload) < 65_000


def test_no_cluster_dict_has_tests_key() -> None:
    """AC1, AC2: every cluster in metadata uses `members`, never `tests`."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    for cluster in result.metadata["clusters"]:
        assert "members" in cluster
        assert "tests" not in cluster
