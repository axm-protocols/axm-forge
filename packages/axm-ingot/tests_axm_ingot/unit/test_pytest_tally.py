from __future__ import annotations

import axm_ingot
import axm_ingot.pytest_tally
from axm_ingot import tally_outcomes


def test_mixed_listing_tallies_exact_per_kind_counts() -> None:
    """AC1: mixed FAILED/ERROR/SKIPPED listing yields exact per-kind counts."""
    result = tally_outcomes(["FAILED a", "FAILED b", "ERROR c", "SKIPPED d"])
    assert result == {"failed": 2, "error": 1, "skipped": 1, "unknown": 0}


def test_realistic_short_summary_block_tallies_exact_counts() -> None:
    """AC1: a realistic short-summary block tallies its known per-kind totals."""
    block = (
        "=== short test summary info ===\n"
        "FAILED tests/unit/test_a.py::test_one - AssertionError\n"
        "FAILED tests/unit/test_b.py::test_two - ValueError\n"
        "FAILED tests/unit/test_c.py::test_three - KeyError\n"
        "ERROR tests/unit/test_d.py::test_four - fixture error\n"
        "SKIPPED [1] tests/unit/test_e.py:12: needs network\n"
        "SKIPPED [1] tests/unit/test_f.py:20: slow\n"
    )
    lines = block.splitlines()
    result = tally_outcomes(lines)
    assert result["failed"] == 3
    assert result["error"] == 1
    assert result["skipped"] == 2


def test_unrecognised_line_lands_in_unknown_bucket() -> None:
    """AC2: lines with an unknown leading keyword go to unknown, never dropped."""
    result = tally_outcomes(["PASSED x", "garbage"])
    assert result["unknown"] == 2


def test_empty_sequence_yields_zero_tally() -> None:
    """AC3: an empty sequence yields a zero tally for every bucket."""
    result = tally_outcomes([])
    assert result == {"failed": 0, "error": 0, "skipped": 0, "unknown": 0}


def test_malformed_elements_counted_unknown_never_raise() -> None:
    """AC2, AC3: None/non-string/empty elements are counted unknown, never raise."""
    result = tally_outcomes([None, 123, ""])
    assert result["unknown"] >= 1


def test_matching_is_case_insensitive_and_whitespace_tolerant() -> None:
    """AC4: leading whitespace and lower-case keywords still match the bucket."""
    result = tally_outcomes(["  failed foo", "FAILED bar"])
    assert result["failed"] == 2


def test_root_reexport_is_module_symbol_and_in_all() -> None:
    """AC5: package-root re-export is the module symbol and named in __all__."""
    assert axm_ingot.tally_outcomes is axm_ingot.pytest_tally.tally_outcomes
    assert "tally_outcomes" in axm_ingot.__all__
