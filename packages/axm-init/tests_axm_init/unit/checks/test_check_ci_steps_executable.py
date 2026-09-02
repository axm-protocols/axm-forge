"""Unit tests for semantic CI step validation."""

from __future__ import annotations

from axm_init.checks import ci


def test_invalid_step_entries_reports_scalar_with_job_name() -> None:
    """AC1: a scalar step is reported with its job name and raw value."""
    workflow = {
        "jobs": {
            "test": {
                "steps": [
                    {"run": "pytest"},
                    "axm-audit",
                ]
            }
        }
    }

    invalid = ci._invalid_step_entries(workflow)

    assert len(invalid) == 1
    assert "test" in invalid[0]
    assert "axm-audit" in invalid[0]


def test_invalid_step_entries_accepts_decorated_executable_steps() -> None:
    """AC2: decorated uses/run steps stay valid while an orphan mapping fails."""
    workflow = {
        "jobs": {
            "test": {
                "steps": [
                    {
                        "name": "checkout decorated",
                        "uses": "actions/checkout@v4",
                        "with": {"fetch-depth": 0},
                        "if": "always()",
                    },
                    {
                        "name": "pytest decorated",
                        "run": "pytest",
                        "env": {"PYTHONUTF8": "1"},
                        "continue-on-error": False,
                    },
                ]
            },
            "lint": {"steps": [{"name": "orphan"}]},
        }
    }

    invalid = ci._invalid_step_entries(workflow)

    assert len(invalid) == 1
    assert "lint" in invalid[0]
    assert all("checkout decorated" not in entry for entry in invalid)
    assert all("pytest decorated" not in entry for entry in invalid)
