"""Pure metadata rejection precedes resource inspection."""

from __future__ import annotations

from pathlib import Path

from axm_init.checks._shared_ticket import shared_ticket_findings


def test_shared_ticket_without_declared_unit_is_unresolved() -> None:
    units: list[dict[str, object]] = [
        {
            "name": "run",
            "protocols": [{"action": "exec", "unit_ticket": "ml.run"}],
        }
    ]
    assert shared_ticket_findings(Path("unread-resource"), "ml", units, {}) == [
        "pyproject.toml: unresolved unit_ticket"
    ]


def test_partial_shared_ticket_binding_is_invalid_before_resource_inspection() -> None:
    units: list[dict[str, object]] = [
        {
            "name": "run",
            "contracts": [],
            "entry_action": "exec",
            "protocols": [],
        }
    ]
    findings = shared_ticket_findings(Path("unread-resource"), "ml", units, {})
    assert len(findings) == 1
    assert findings[0].startswith("pyproject.toml: invalid shared unit:")
    assert "ticket_type" in findings[0]


def test_legacy_unit_without_shared_consumers_needs_no_resource_inspection() -> None:
    units: list[dict[str, object]] = [
        {
            "name": "run",
            "protocols": [{"action": "exec", "ticket_type": "ml.old"}],
        }
    ]
    assert shared_ticket_findings(Path("unread-resource"), "ml", units, {}) == []
