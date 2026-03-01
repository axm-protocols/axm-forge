"""Base class for project rules — dependency-free module.

This module contains the abstract base class for all rules.
It has no dependencies on concrete rule implementations to avoid circular imports.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from axm_audit.models.results import CheckResult

# ── Shared scoring constants ──────────────────────────────────────────
#
# Scoring convention
# ~~~~~~~~~~~~~~~~~~
# Every rule starts at 100 and deducts a fixed penalty per violation.
# The formula is always ``max(0, 100 - count * penalty)``.
# Ratio-based rules compute ``int(coverage * 100)`` instead.
#
# ┌─────────────────────┬─────────┬──────────────────────────┐
# │ Rule ID             │ Penalty │ Unit                     │
# ├─────────────────────┼─────────┼──────────────────────────┤
# │ QUALITY_LINT        │  2      │ per lint issue           │
# │ QUALITY_FORMAT      │  5      │ per unformatted file     │
# │ QUALITY_TYPE        │  5      │ per type error           │
# │ QUALITY_COMPLEXITY  │ 10      │ per high-CC function     │
# │ QUALITY_DIFF_SIZE   │ linear  │ 100→0 over [200,800] LOC │
# │ QUALITY_SECURITY    │ 15/5    │ per HIGH/MEDIUM finding  │
# │ QUALITY_COVERAGE    │ ratio   │ branch coverage %        │
# │ DEPS_AUDIT          │ 15      │ per vulnerable package   │
# │ DEPS_HYGIENE        │ 10      │ per hygiene issue        │
# │ ARCH_CIRCULAR       │ 20      │ per cycle                │
# │ ARCH_GOD_CLASS      │ 15      │ per god class            │
# │ ARCH_COUPLING       │  5      │ per over-coupled module  │
# │ ARCH_DUPLICATION    │ 10      │ per duplicate pair       │
# │ PRACTICE_DOCSTRING  │ ratio   │ docstring coverage %     │
# │ PRACTICE_BARE_EXCEPT│ 20      │ per bare except          │
# │ PRACTICE_SECURITY   │ 25      │ per hardcoded secret     │
# │ PRACTICE_BLOCKING_IO│ 15      │ per blocking I/O call    │
# │                     │         │ (time.sleep in async +   │
# │                     │         │  HTTP without timeout)   │
# │ PRACTICE_LOGGING    │ ratio   │ logging coverage %       │
# │ PRACTICE_TEST_MIRROR│ 15      │ per untested module      │
# │ STRUCTURE_PYPROJECT │ binary  │ field presence checks    │
# └─────────────────────┴─────────┴──────────────────────────┘
#
# Pass threshold: score >= 90 to pass.

PASS_THRESHOLD: int = 90
"""Minimum score (out of 100) for a check to pass."""

COMPLEXITY_THRESHOLD: int = 10
"""Cyclomatic complexity ceiling — functions at or above are flagged."""

PERFECT_SCORE: int = 100
"""Maximum achievable score."""


class ProjectRule(ABC):
    """Base class for project invariants.

    Each rule defines a single check that a project must satisfy.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Unique identifier for this rule."""

    @abstractmethod
    def check(self, project_path: Path) -> CheckResult:
        """Execute the check against a project.

        Args:
            project_path: Root directory of the project to check.

        Returns:
            CheckResult with pass/fail status and message.
        """
