"""Experiment checks — the FORM of an experiment folder, never its substance.

axm-init grades the SHAPE a scaffolded experiment must carry: the five
working directories and the two root files. The substance (manifest
validity, input hashing, DAG coherence, freeze anteriority, metrics) is the
job of a dedicated tool in another package — duplicating it here would be an
architecture regression, so no check in this module ever reads the CONTENT
of ``manifest.yaml``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from axm_init.models.check import CheckResult

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["check_experiment_files", "check_experiment_structure"]

_REQUIRED_DIRS: tuple[str, ...] = (
    "inputs",
    "scripts",
    "outputs",
    "analysis",
    "figures",
)

_REQUIRED_FILES: tuple[str, ...] = ("manifest.yaml", "README.md")


def _missing_entries(required: tuple[str, ...], present: set[str]) -> list[str]:
    """Return the *required* names absent from *present*, in declaration order.

    Pure list logic, deliberately filesystem-free: the caller resolves what
    exists on disk, this helper only decides what is missing.

    Args:
        required: The entries the experiment folder must carry, in the order
            they should be reported.
        present: The subset of names actually found.

    Returns:
        The missing names, in ``required`` order (empty when nothing misses).
    """
    return [name for name in required if name not in present]


def check_experiment_structure(project: Path) -> CheckResult:
    """Check: the experiment folder carries the five working directories.

    Args:
        project: Experiment root directory.

    Returns:
        A failed ``CheckResult`` naming exactly the missing directories, or
        a passed one.
    """
    present = {name for name in _REQUIRED_DIRS if (project / name).is_dir()}
    missing = _missing_entries(_REQUIRED_DIRS, present)
    if missing:
        listed = ", ".join(f"{name}/" for name in missing)
        return CheckResult(
            name="experiment.experiment_structure",
            category="experiment",
            passed=False,
            weight=5,
            message=(
                f"Experiment layout missing {len(missing)} directory(ies): {listed}"
            ),
            details=[f"Missing: {listed}"],
            fix=(
                "Create inputs/, scripts/, outputs/, analysis/ and figures/ "
                "at the experiment root."
            ),
        )
    return CheckResult(
        name="experiment.experiment_structure",
        category="experiment",
        passed=True,
        weight=5,
        message=(
            "Experiment layout complete "
            "(inputs/, scripts/, outputs/, analysis/, figures/)"
        ),
        details=[],
        fix="",
    )


def check_experiment_files(project: Path) -> CheckResult:
    """Check: ``manifest.yaml`` and ``README.md`` exist at the experiment root.

    Existence only — the manifest CONTENT is never parsed here, so a freshly
    scaffolded experiment whose manifest still holds TODO placeholders
    passes this form check.

    Args:
        project: Experiment root directory.

    Returns:
        A failed ``CheckResult`` naming exactly the missing file(s), or a
        passed one.
    """
    present = {name for name in _REQUIRED_FILES if (project / name).is_file()}
    missing = _missing_entries(_REQUIRED_FILES, present)
    if missing:
        listed = ", ".join(missing)
        return CheckResult(
            name="experiment.experiment_files",
            category="experiment",
            passed=False,
            weight=5,
            message=f"Experiment root missing {len(missing)} file(s): {listed}",
            details=[f"Missing: {listed}"],
            fix="Create manifest.yaml and README.md at the experiment root.",
        )
    return CheckResult(
        name="experiment.experiment_files",
        category="experiment",
        passed=True,
        weight=5,
        message="Experiment root carries manifest.yaml and README.md",
        details=[],
        fix="",
    )
