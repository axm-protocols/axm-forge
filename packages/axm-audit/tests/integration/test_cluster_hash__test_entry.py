"""Split from ``test_duplicate_tests_acknowledgement.py``."""

import textwrap
from pathlib import Path

from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsRule,
    _cluster_hash,
    _TestEntry,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


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


def test_cluster_hash_consistency_via_public_boundary(project: Path) -> None:
    """Sanity check: hashing a slim cluster matches what the rule emits."""
    _write_two_duplicates(project)
    result = DuplicateTestsRule().check(project)
    cluster = result.metadata["clusters"][0]
    # Reconstruct a raw-shape cluster (tests with file+name only) and re-hash.
    members: list[_TestEntry] = [
        {"file": m["file"], "name": m["name"], "line": m.get("line", 0)}
        for m in cluster["members"]
    ]
    expected = _cluster_hash(
        {"signal": cluster["signal"], "similarity": 1.0, "members": members}
    )
    assert cluster["cluster_hash"] == expected
