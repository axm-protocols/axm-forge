"""Integration tests for hash-based duplicate-test cluster acknowledgement (axm-1727).

Drives `DuplicateTestsRule().check(project)` end-to-end through pyproject.toml
config loading. Internal helpers (`_cluster_hash`, `_load_duplicate_tests_config`,
`_slim_clusters`) are exercised transitively.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsRule,
    _cluster_hash,
)

pytestmark = pytest.mark.integration


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    return tmp_path


def _write_two_duplicates(project: Path) -> None:
    """Two structurally-identical tests in one file → one cluster."""
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_parse_one():
            result = parse(1)
            assert result == 1
            assert result > 0

        def test_parse_two():
            result = parse(2)
            assert result == 1
            assert result > 0
        """,
    )


def _write_two_distinct_clusters(project: Path) -> None:
    """Two clusters of duplicates in separate files."""
    _write(
        project / "tests" / "test_mod_a.py",
        """
        def test_parse_one():
            result = parse(1)
            assert result == 1
            assert result > 0

        def test_parse_two():
            result = parse(2)
            assert result == 1
            assert result > 0
        """,
    )
    _write(
        project / "tests" / "test_mod_b.py",
        """
        def test_render_alpha():
            html = render("alpha")
            assert "<div>" in html
            assert len(html) > 10

        def test_render_beta():
            html = render("beta")
            assert "<div>" in html
            assert len(html) > 10
        """,
    )


def _first_cluster_hash(project: Path) -> str:
    """Run the rule with no config and return the first cluster's hash."""
    result = DuplicateTestsRule().check(project)
    clusters: list[dict[str, Any]] = list(result.metadata["clusters"])
    assert clusters, "setup error: expected at least one cluster"
    return str(clusters[0]["cluster_hash"])


def _write_pyproject_with_ack(project: Path, entries: list[tuple[str, str]]) -> None:
    lines = ["[tool.axm-audit.duplicate_tests]"]
    for h, reason in entries:
        lines += [
            "",
            "[[tool.axm-audit.duplicate_tests.acknowledged]]",
            f'hash = "{h}"',
            f'reason = "{reason}"',
        ]
    (project / "pyproject.toml").write_text("\n".join(lines) + "\n")


def test_no_pyproject_keeps_clusters_flagged(project: Path) -> None:
    """AC2: missing pyproject.toml → empty acknowledgement list, no error."""
    _write_two_duplicates(project)
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert "config_error" not in result.metadata


def test_pyproject_without_section_keeps_clusters_flagged(project: Path) -> None:
    """AC2: pyproject without `[tool.axm-audit.duplicate_tests]` → no error."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.0"\n'
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert "config_error" not in result.metadata


def test_acknowledged_cluster_excluded_from_score(project: Path) -> None:
    """AC3, AC5: acknowledged cluster → passed=True, score=100, marked."""
    _write_two_duplicates(project)
    h = _first_cluster_hash(project)
    _write_pyproject_with_ack(project, [(h, "validated: distinct fixtures")])

    result = DuplicateTestsRule().check(project)
    assert result.passed is True
    assert result.score == 100
    ack = next(c for c in result.metadata["clusters"] if c["cluster_hash"] == h)
    assert ack["acknowledged"] is True


def test_unacknowledged_cluster_still_lowers_score(project: Path) -> None:
    """AC3: empty acknowledged list → cluster still flagged."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        "[tool.axm-audit.duplicate_tests]\nacknowledged = []\n"
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert result.score < 100
    cluster = result.metadata["clusters"][0]
    assert cluster.get("acknowledged", False) is False


def test_partial_acknowledgement_isolates_remaining_clusters(
    project: Path,
) -> None:
    """AC3: acknowledging one of two clusters leaves the other flagged."""
    _write_two_distinct_clusters(project)
    result0 = DuplicateTestsRule().check(project)
    hashes = [c["cluster_hash"] for c in result0.metadata["clusters"]]
    assert len(hashes) >= 2, f"expected ≥2 clusters, got {hashes}"
    ack_hash, other_hash = hashes[0], hashes[1]

    _write_pyproject_with_ack(project, [(ack_hash, "validated")])
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    by_hash = {c["cluster_hash"]: c for c in result.metadata["clusters"]}
    assert by_hash[ack_hash]["acknowledged"] is True
    assert by_hash[other_hash].get("acknowledged", False) is False


def test_stale_acknowledged_hash_listed_in_metadata(project: Path) -> None:
    """AC4, AC5: stale hash → metadata.stale_acknowledged, no score impact."""
    _write_two_duplicates(project)
    fake_hash = "deadbeef0000"
    _write_pyproject_with_ack(
        project, [(fake_hash, "old entry from a deleted cluster")]
    )
    result_with_stale = DuplicateTestsRule().check(project)

    # Score must be identical to no-config baseline (stale entries don't help).
    (project / "pyproject.toml").unlink()
    baseline = DuplicateTestsRule().check(project)

    stale = result_with_stale.metadata.get("stale_acknowledged", [])
    stale_hashes = [entry["hash"] for entry in stale]
    assert fake_hash in stale_hashes
    assert result_with_stale.passed is False
    assert result_with_stale.score == baseline.score


def test_stale_acknowledged_rendered_in_text(project: Path) -> None:
    """AC4: stale entries appear as bullet lines in result.text."""
    _write_two_duplicates(project)
    fake_hash = "deadbeef0000"
    _write_pyproject_with_ack(project, [(fake_hash, "old reason")])

    result = DuplicateTestsRule().check(project)
    assert fake_hash in result.text
    assert "stale acknowledged cluster" in result.text


def test_malformed_toml_falls_back_gracefully(project: Path) -> None:
    """AC6: malformed TOML → metadata.config_error, audit does not crash."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        "[tool.axm-audit.duplicate_tests\nnot valid toml\n"
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    err = result.metadata.get("config_error")
    assert isinstance(err, str)
    assert err


def test_wrong_schema_falls_back_gracefully(project: Path) -> None:
    """AC2, AC6: malformed schema (missing `reason`) → config_error, baseline score."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        '[[tool.axm-audit.duplicate_tests.acknowledged]]\nhash = "a1b2c3d4e5f6"\n'
    )
    result = DuplicateTestsRule().check(project)

    (project / "pyproject.toml").unlink()
    baseline = DuplicateTestsRule().check(project)

    assert result.passed is False
    err = result.metadata.get("config_error")
    assert isinstance(err, str)
    assert "schema" in err.lower()
    assert result.score == baseline.score


def test_well_formed_two_entries_round_trip(project: Path) -> None:
    """AC2: two valid acknowledgements → both clusters marked, no error."""
    _write_two_distinct_clusters(project)
    baseline = DuplicateTestsRule().check(project)
    hashes = [c["cluster_hash"] for c in baseline.metadata["clusters"]]
    assert len(hashes) >= 2
    h1, h2 = hashes[0], hashes[1]

    _write_pyproject_with_ack(project, [(h1, "validated A"), (h2, "validated B")])

    result = DuplicateTestsRule().check(project)
    assert result.passed is True
    assert "config_error" not in result.metadata
    by_hash = {c["cluster_hash"]: c for c in result.metadata["clusters"]}
    assert by_hash[h1]["acknowledged"] is True
    assert by_hash[h2]["acknowledged"] is True


def test_cluster_hash_consistency_via_public_boundary(project: Path) -> None:
    """Sanity check: hashing a slim cluster matches what the rule emits."""
    _write_two_duplicates(project)
    result = DuplicateTestsRule().check(project)
    cluster = result.metadata["clusters"][0]
    # Reconstruct a raw-shape cluster (tests with file+name only) and re-hash.
    members: list[dict[str, Any]] = [
        {"file": m["file"], "name": m["name"], "line": m.get("line", 0)}
        for m in cluster.get("members", cluster.get("tests", []))
    ]
    expected = _cluster_hash(
        {"signal": cluster["signal"], "similarity": 1.0, "tests": members}  # type: ignore[typeddict-item]
    )
    assert cluster["cluster_hash"] == expected
