"""Base class for project rules — dependency-free module.

This module contains the abstract base class for all rules,
the ``@register_rule`` decorator, and the shared ``_RULE_REGISTRY``.
It has no dependencies on concrete rule implementations to avoid circular imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from axm_audit.models.results import CheckResult, Severity

if TYPE_CHECKING:
    from collections.abc import Callable

# ── Auto-discovery registry ───────────────────────────────────────────
#
# Rule classes decorate themselves with ``@register_rule("lint")``
# at import time.  The auditor reads ``get_registry()`` instead of a
# hardcoded dict.  The decorator also injects ``_registered_category``
# so that ``ProjectRule.category`` resolves without a manual property.

_RULE_REGISTRY: dict[str, list[type[ProjectRule]]] = {}


def register_rule(category: str) -> Callable[[type[ProjectRule]], type[ProjectRule]]:
    """Class decorator that registers a rule in the auto-discovery registry.

    Also injects ``_registered_category`` on the class so that
    ``ProjectRule.category`` resolves automatically.

    Args:
        category: Unified category (e.g. ``"lint"``, ``"security"``).

    Returns:
        The unmodified class — the decorator only appends to the registry
        and sets the ``_registered_category`` attribute.
    """

    def _decorator(cls: type[ProjectRule]) -> type[ProjectRule]:
        cls._registered_category = category  # type: ignore[attr-defined]
        bucket = _RULE_REGISTRY.setdefault(category, [])
        if cls not in bucket:
            bucket.append(cls)
        return cls

    return _decorator


def get_registry() -> dict[str, list[type[ProjectRule]]]:
    """Return the current rule registry (read-only view).

    Callers must ensure that rule modules have been imported before
    calling this function so that ``@register_rule`` decorators have
    fired.
    """
    return _RULE_REGISTRY


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

    @property
    def category(self) -> str:
        """Scoring category, auto-injected by ``@register_rule``.

        Valid values: ``lint``, ``type``, ``complexity``, ``security``,
        ``deps``, ``testing``, ``architecture``, ``practices``,
        ``structure``, ``tooling``.
        """
        return getattr(self, "_registered_category", "")

    @abstractmethod
    def check(self, project_path: Path) -> CheckResult:
        """Execute the check against a project.

        Args:
            project_path: Root directory of the project to check.

        Returns:
            CheckResult with pass/fail status and message.
        """

    def check_src(self, project_path: Path) -> CheckResult | None:
        """Return an early ``CheckResult`` if ``src/`` does not exist.

        Call this at the top of ``check()`` to eliminate boilerplate::

            early = self.check_src(project_path)
            if early is not None:
                return early

        Returns:
            ``None`` if ``src/`` exists (rule should continue).
            A passing ``CheckResult`` if ``src/`` is missing.
        """
        src_path = project_path / "src"
        if src_path.exists():
            return None
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="src/ directory not found",
            severity=Severity.INFO,
            details={"score": 100},
        )

    @classmethod
    def get_instances(cls) -> list[ProjectRule]:
        """Instantiate this rule.

        Override in subclasses that require constructor parameters
        (e.g. ``ToolAvailabilityRule``).

        Returns:
            List of rule instances — ``[cls()]`` by default.
        """
        return [cls()]
