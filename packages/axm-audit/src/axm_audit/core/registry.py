"""Re-export of the rule registry accessors.

Thin shim exposing :func:`get_registry`, :func:`register_rule` and the
underlying ``_RULE_REGISTRY`` from :mod:`axm_audit.core.rules.base` at a
shorter import path.
"""

from __future__ import annotations

from axm_audit.core.rules.base import (
    _RULE_REGISTRY,
    ProjectRule,
    get_registry,
    register_rule,
)

__all__ = ["_RULE_REGISTRY", "ProjectRule", "get_registry", "register_rule"]
