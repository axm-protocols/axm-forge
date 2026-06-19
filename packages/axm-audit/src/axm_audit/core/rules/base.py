"""Base class for project rules — dependency-free module.

This module contains the abstract base class for all rules,
the ``@register_rule`` decorator, and the shared ``_RULE_REGISTRY``.
It has no dependencies on concrete rule implementations to avoid circular imports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from axm_audit.core.framework import Framework
from axm_audit.core.rules._helpers import iter_src_dirs
from axm_audit.models.results import CheckResult, Severity

if TYPE_CHECKING:
    from collections.abc import Callable

# ── Auto-discovery registry ───────────────────────────────────────────
#
# Rule classes decorate themselves with ``@register_rule("lint")``
# at import time.  The auditor reads the registry instead of a hardcoded
# dict.  The decorator also injects ``_registered_category`` and
# ``_registered_framework`` so that ``ProjectRule.category`` /
# ``ProjectRule.framework`` resolve without a manual property.
#
# The registry is keyed by ``(category, framework)``. ``framework`` defaults
# to ``"python"`` so every existing Python rule keeps its exact behaviour
# without touching its decorator.

_RULE_REGISTRY: dict[tuple[str, Framework], list[type[ProjectRule]]] = {}


def register_rule(
    category: str,
    framework: Framework | str = Framework.PYTHON,
) -> Callable[[type[ProjectRule]], type[ProjectRule]]:
    """Class decorator that registers a rule in the auto-discovery registry.

    Also injects ``_registered_category`` and ``_registered_framework`` on the
    class so that ``ProjectRule.category`` / ``ProjectRule.framework`` resolve
    automatically.

    Args:
        category: Unified category (e.g. ``"lint"``, ``"security"``).
        framework: Ecosystem the rule applies to (default ``"python"`` so
            existing Python rules are unaffected).

    Returns:
        The unmodified class — the decorator only appends to the registry
        and sets the ``_registered_*`` attributes.
    """
    fw = Framework(framework)

    def _decorator(cls: type[ProjectRule]) -> type[ProjectRule]:
        cls._registered_category = category  # type: ignore[attr-defined]
        cls._registered_framework = fw  # type: ignore[attr-defined]
        bucket = _RULE_REGISTRY.setdefault((category, fw), [])
        if cls not in bucket:
            bucket.append(cls)
        return cls

    return _decorator


def get_registry() -> dict[str, list[type[ProjectRule]]]:
    """Return the Python rule registry as a ``category -> classes`` view.

    Backwards-compatible accessor: it exposes only the ``python`` framework
    rules, keyed by category, exactly as before the framework dimension was
    introduced. New framework-aware callers use :func:`get_registry_for`.

    Callers must ensure that rule modules have been imported before
    calling this function so that ``@register_rule`` decorators have fired.
    """
    return get_registry_for(Framework.PYTHON)


def get_registry_for(framework: Framework) -> dict[str, list[type[ProjectRule]]]:
    """Return the rule registry for a single *framework*, keyed by category.

    Args:
        framework: Ecosystem whose rules to expose.

    Returns:
        Mapping ``category -> [rule classes]`` for that framework only.
    """
    view: dict[str, list[type[ProjectRule]]] = {}
    for (category, fw), classes in _RULE_REGISTRY.items():
        if fw is framework:
            view.setdefault(category, []).extend(classes)
    return view


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
# │ QUALITY_DIFF_SIZE   │ linear  │ 100→0 over [400,1200] LOC│
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
# │ TEST_PYRAMID_LEVEL  │ ratio   │ tests at correct level   │
# │ TEST_TAUTOLOGY      │ ratio   │ non-tautological tests   │
# │ TEST_PRIVATE_IMPORT │ ratio   │ public-API imports       │
# │ TEST_DUPLICATE      │ ratio   │ unique test bodies       │
# │ STRUCTURE_PYPROJECT │ binary  │ field presence checks    │
# │ TOOL_<NAME>         │ binary  │ CLI tool availability    │
# └─────────────────────┴─────────┴──────────────────────────┘
#
# Composite quality score = weighted average of 9 scored categories.
# Structure (handled by axm-init) and tooling are NOT scored.
# Pass threshold: composite score >= 90 to pass.

PASS_THRESHOLD: int = 90
"""Minimum score (out of 100) for a check to pass."""

LINT_PASS_THRESHOLD: int = 100
"""Minimum lint score — zero tolerance for lint issues."""


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

    @property
    def framework(self) -> Framework:
        """Ecosystem this rule applies to, auto-injected by ``@register_rule``.

        Defaults to :attr:`Framework.PYTHON` for rules registered before the
        framework dimension existed.
        """
        return getattr(self, "_registered_framework", Framework.PYTHON)

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
            ``None`` if ``src/`` exists — single-package layout (``src/``)
            or multi-package workspace (``packages/*/src/``). The rule
            should continue.
            A passing ``CheckResult`` if neither layout is present.
        """
        if iter_src_dirs(project_path):
            return None
        return CheckResult(
            rule_id=self.rule_id,
            passed=True,
            message="src/ directory not found",
            severity=Severity.INFO,
            score=100,
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
