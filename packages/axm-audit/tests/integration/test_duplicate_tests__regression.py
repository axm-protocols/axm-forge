"""Regression gate for AXM-2175: moving Jaccard fns to ``axm_echo``.

The move replaces the local copies of ``statement_set`` /
``jaccard_similarity`` / ``normalize_dump`` in ``duplicate_tests`` with a
direct import from ``axm_echo``. The contract is that the *finding* the rule
emits stays byte-identical and that existing waivers keep matching.
"""

from __future__ import annotations

from pathlib import Path

import axm_echo
import pytest

from axm_audit.core.rules.test_quality import duplicate_tests
from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule

# Golden snapshot of the finding for a known 1-pair duplicate cluster,
# captured from the pre-move implementation (local Jaccard copies). The move
# is a pure relocation, so these values MUST be reproduced exactly.
_DUP_BODY = (
    "def test_parse_one():\n"
    "    result = parse(1)\n"
    "    assert result == 1\n"
    "    assert result > 0\n"
    "\n"
    "\n"
    "def test_parse_two():\n"
    "    result = parse(2)\n"
    "    assert result == 1\n"
    "    assert result > 0\n"
)
_GOLDEN_CLUSTER_HASH = "8d8227469c27"
_GOLDEN_SIGNAL = "signal1_call_assert"
_GOLDEN_MEMBERS = [
    ("tests/test_mod.py", "test_parse_one"),
    ("tests/test_mod.py", "test_parse_two"),
]


def _write_known_cluster(project: Path) -> None:
    """Write the deterministic duplicate pair the golden snapshot pins."""
    (project / "tests" / "test_mod.py").write_text(_DUP_BODY, encoding="utf-8")


@pytest.mark.integration
def test_imports_from_echo_not_local() -> None:
    """AC1: duplicate_tests reuses the echo Jaccard fns, not local copies.

    The three structural helpers the rule binds (``statement_set`` /
    ``jaccard_similarity`` / ``normalize_dump``, kept under the module's
    established ``_``-aliased names) are the *exact same objects* exported by
    ``axm_echo`` and defined in the ``axm_echo`` package — proving there is no
    surviving local copy. The module and tests share the ``axm_audit`` package,
    so reading the aliases is a same-package access.
    """
    bindings = {
        "statement_set": duplicate_tests._statement_set,
        "jaccard_similarity": duplicate_tests._jaccard_similarity,
        "normalize_dump": duplicate_tests._normalize_dump,
    }
    for echo_name, bound in bindings.items():
        echo = getattr(axm_echo, echo_name)
        assert bound is echo, f"{echo_name} is not the axm_echo object"
        assert bound.__module__.startswith("axm_echo"), (
            f"{echo_name} resolves to {bound.__module__}, expected an axm_echo module"
        )


@pytest.mark.integration
def test_finding_byte_identical_after_move(project: Path) -> None:
    """AC3: the finding is byte-identical to the pre-move golden snapshot.

    Same clusters, same signal, same member set, same order-independent
    ``cluster_hash`` — the GATE proving the move did not change the contract.
    """
    _write_known_cluster(project)

    result = DuplicateTestsRule().check(project)
    clusters = result.metadata["clusters"]

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["cluster_hash"] == _GOLDEN_CLUSTER_HASH
    assert cluster["signal"] == _GOLDEN_SIGNAL
    members = sorted((m["file"], m["name"]) for m in cluster["members"])
    assert members == _GOLDEN_MEMBERS
    assert result.passed is False
    assert result.score == 95


@pytest.mark.integration
def test_existing_waiver_survives(project: Path) -> None:
    """AC4: a waiver keyed on the pre-move hash still excludes its cluster.

    The acknowledgement hash is order-independent (members sorted before
    hashing), so the relocation cannot invalidate it. The waived cluster is
    marked acknowledged and the rule passes.
    """
    _write_known_cluster(project)
    (project / "pyproject.toml").write_text(
        "[tool.axm-audit.duplicate_tests]\n"
        "\n"
        "[[tool.axm-audit.duplicate_tests.acknowledged]]\n"
        f'hash = "{_GOLDEN_CLUSTER_HASH}"\n'
        'reason = "validated: distinct fixtures"\n',
        encoding="utf-8",
    )

    result = DuplicateTestsRule().check(project)

    assert result.passed is True
    assert result.score == 100
    cluster = next(
        c
        for c in result.metadata["clusters"]
        if c["cluster_hash"] == _GOLDEN_CLUSTER_HASH
    )
    assert cluster["acknowledged"] is True
    assert "config_error" not in result.metadata
