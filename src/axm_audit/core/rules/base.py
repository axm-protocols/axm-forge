"""Base class for project rules — dependency-free module.

This module contains the abstract base class for all rules.
It has no dependencies on concrete rule implementations to avoid circular imports.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from axm_audit.models.results import CheckResult


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
