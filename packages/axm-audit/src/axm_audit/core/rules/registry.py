"""Re-export of :mod:`axm_audit.core.registry` under ``core.rules.registry``.

Thin shim used by tests that expect the registry accessors to live under
the ``core.rules`` sub-package.
"""

from __future__ import annotations

from axm_audit.core.registry import (
    _RULE_REGISTRY,
    ProjectRule,
    get_registry,
    register_rule,
)

__all__ = ["_RULE_REGISTRY", "ProjectRule", "get_registry", "register_rule"]
