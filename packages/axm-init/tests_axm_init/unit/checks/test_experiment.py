"""Unit tests for the experiment form checks (``axm_init.checks.experiment``)."""

from __future__ import annotations

from axm_init.checks.experiment import (
    _missing_entries,
    check_experiment_files,
    check_experiment_structure,
)
from axm_init.core.checker import _known_check_ids, get_check_name


def test_missing_entries_lists_absent_required_names_in_order() -> None:
    """AC1: the helper returns the required names absent from the present set."""
    required = ("inputs", "scripts", "outputs", "analysis", "figures")

    missing = _missing_entries(required, {"inputs", "figures"})

    assert missing == ["scripts", "outputs", "analysis"]


def test_missing_entries_is_empty_when_everything_is_present() -> None:
    """AC2: nothing is reported missing when every required entry is present."""
    required = ("manifest.yaml", "README.md")

    missing = _missing_entries(required, {"manifest.yaml", "README.md"})

    assert missing == []


def test_experiment_checks_are_registered_under_known_ids() -> None:
    """AC3: both checks are discovered, so their canonical ids are known."""
    known = _known_check_ids()

    names = [
        get_check_name(check_experiment_structure),
        get_check_name(check_experiment_files),
    ]

    assert names == ["experiment.experiment_structure", "experiment.experiment_files"]
    assert set(names) <= set(known)
