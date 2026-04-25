from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from axm_audit.formatters import (
    format_agent,
    format_agent_text,
    format_report,
    format_test_quality_text,
)

pytestmark = pytest.mark.integration

SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "formatters"


def _assert_snapshot(name: str, actual: str) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / name
    if not path.exists():
        path.write_text(actual)
    expected = path.read_text()
    assert actual == expected, f"Snapshot drift for {name}"


@pytest.fixture
def audit_result() -> Any:
    from axm_audit.models import AuditResult

    return AuditResult.model_validate(
        {
            "project_path": "/tmp/sample",
            "quality_score": 75,
            "grade": "B",
            "checks": [
                {
                    "rule_id": "ruff",
                    "message": "ok",
                    "category": "lint",
                    "passed": True,
                },
                {
                    "rule_id": "mypy",
                    "message": "ok",
                    "category": "type",
                    "passed": True,
                },
                {
                    "rule_id": "complexity",
                    "message": "1 function above CC budget",
                    "category": "complexity",
                    "passed": False,
                    "text": "1 function above CC budget",
                    "details": {"hotspots": [{"name": "foo", "cc": 15}]},
                },
                {
                    "rule_id": "TEST_PYRAMID",
                    "message": "pyramid mismatch",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "pyramid_mismatches": [
                            {
                                "test": "tests/unit/test_a.py::test_a",
                                "current_dir": "unit",
                                "detected_level": "integration",
                            },
                            {
                                "test": "tests/unit/test_b.py::test_b",
                                "current_dir": "unit",
                                "detected_level": "unit",
                            },
                        ],
                    },
                },
                {
                    "rule_id": "PRIVATE_IMPORTS",
                    "message": "private imports",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "private_import_violations": [
                            {
                                "file": "tests/unit/test_b.py",
                                "line": 5,
                                "symbol": "_helper",
                            }
                        ],
                    },
                },
                {
                    "rule_id": "duplicates",
                    "message": "duplicates found",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "clusters": [
                            {
                                "signal": "shape:0xabc",
                                "members": [
                                    {
                                        "file": "tests/unit/test_a.py",
                                        "line": 1,
                                        "test": "test_a",
                                    },
                                    {
                                        "file": "tests/unit/test_b.py",
                                        "line": 2,
                                        "test": "test_b",
                                    },
                                ],
                            }
                        ]
                    },
                },
                {
                    "rule_id": "tautologies",
                    "message": "tautologies found",
                    "category": "testing",
                    "passed": False,
                    "metadata": {
                        "verdicts": [
                            {
                                "verdict": "TAUTOLOGY",
                                "test": "test_trivial",
                                "file": "tests/unit/test_c.py",
                                "line": 10,
                            }
                        ]
                    },
                },
            ],
        }
    )


def test_format_agent_text_snapshot_stable(audit_result: Any) -> None:
    data = format_agent(audit_result)
    actual = format_agent_text(data, category="quality")
    _assert_snapshot("format_agent_text.txt", actual)


def test_format_test_quality_text_snapshot_stable(audit_result: Any) -> None:
    actual = format_test_quality_text(audit_result)
    _assert_snapshot("format_test_quality_text.txt", actual)


def test_format_report_snapshot_stable(audit_result: Any) -> None:
    actual = format_report(audit_result)
    _assert_snapshot("format_report.txt", actual)
