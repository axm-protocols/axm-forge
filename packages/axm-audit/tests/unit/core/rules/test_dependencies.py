"""Unit tests for dependency text format helpers (deptry label mapping)."""

from __future__ import annotations

from axm_audit.core.rules.dependencies import _DEPTRY_LABELS


class TestUnitScope:
    def test_deptry_labels_known_codes(self):
        expected = {
            "DEP001": "missing dep",
            "DEP002": "unused dep",
            "DEP003": "transitive dep",
            "DEP004": "misplaced dev dep",
        }
        for code, label in expected.items():
            assert _DEPTRY_LABELS.get(code) == label, f"{code} should map to {label!r}"

    def test_deptry_labels_unknown_fallback(self):
        assert _DEPTRY_LABELS.get("DEP999", "original msg") == "original msg"
