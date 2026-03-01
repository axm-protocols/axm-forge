"""Base class for project rules — dependency-free module.

This module contains the abstract base class for all rules.
It has no dependencies on concrete rule implementations to avoid circular imports.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from axm_audit.models.results import CheckResult

# ── Shared scoring constants ──────────────────────────────────────────
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
