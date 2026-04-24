"""Byte-identical snapshot test for ``format_test_quality_text``.

Guards the refactor that splits the formatter into four section helpers:
the output must not change for an ``AuditResult`` carrying one entry per
section (private, pyramid, duplicate, tautology).
"""

from __future__ import annotations

import pytest

from axm_audit.formatters import format_test_quality_text
from axm_audit.models.results import AuditResult, CheckResult


@pytest.fixture
def result_one_per_section() -> AuditResult:
    """AuditResult exercising every branch of ``format_test_quality_text``."""
    return AuditResult(
        checks=[
            CheckResult(
                rule_id="QUALITY_TEST_PRIVATE_IMPORTS",
                passed=False,
                message="private import",
                metadata={
                    "private_import_violations": [
                        {
                            "file": "tests/unit/foo.py",
                            "line": 10,
                            "symbol": "mypkg._private",
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_PYRAMID",
                passed=False,
                message="pyramid mismatch",
                metadata={
                    "pyramid_mismatches": [
                        {
                            "test": "tests/unit/test_bar.py::test_x",
                            "current_dir": "unit",
                            "detected_level": "integration",
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_DUPLICATES",
                passed=False,
                message="duplicates",
                metadata={
                    "clusters": [
                        {
                            "signal": "call_sig",
                            "members": [
                                {
                                    "test": "test_a",
                                    "file": "tests/unit/a.py",
                                    "line": 5,
                                }
                            ],
                        }
                    ],
                },
            ),
            CheckResult(
                rule_id="QUALITY_TEST_TAUTOLOGY",
                passed=False,
                message="tautology",
                metadata={
                    "verdicts": [
                        {
                            "verdict": "TAUTOLOGY",
                            "test": "test_c",
                            "file": "tests/unit/c.py",
                            "line": 15,
                        }
                    ],
                },
            ),
        ]
    )


SNAPSHOT = (
    "Private imports:\n"
    "  tests/unit/foo.py:10  mypkg._private\n"
    "\n"
    "Pyramid:\n"
    "  tests/unit/test_bar.py::test_x  unit -> integration  [MISMATCH]\n"
    "\n"
    "Duplicates:\n"
    "  [call_sig]\n"
    "    tests/unit/a.py:5  test_a\n"
    "\n"
    "Tautologies:\n"
    "  [TAUTOLOGY] test_c  tests/unit/c.py:15"
)


def test_format_test_quality_text_byte_identical_after_refactor(
    result_one_per_section: AuditResult,
) -> None:
    """Full-mode output must byte-match the pre-refactor snapshot (AC2)."""
    assert format_test_quality_text(result_one_per_section) == SNAPSHOT
