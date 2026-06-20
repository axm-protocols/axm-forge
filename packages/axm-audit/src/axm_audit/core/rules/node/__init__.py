"""Node/Svelte/React rule implementations (the shared ``node`` base layer).

These rules port the *intent* of the Python rules to the Node ecosystem
(ESLint, tsc, prettier, vitest, npm audit, …) without changing axm-audit's
scoring, categories, or ``CheckResult`` contract. They register themselves
under the ``node`` framework via ``@register_rule(category, framework=NODE)``;
UI frameworks (svelte, react) inherit them via ``resolve_frameworks``.

Importing this package fires the ``@register_rule`` decorators (side effect).
"""

from __future__ import annotations

from axm_audit.core.rules.node.format import NodeFormatRule
from axm_audit.core.rules.node.lint import NodeLintRule
from axm_audit.core.rules.node.typecheck import NodeTypeCheckRule

__all__ = ["NodeFormatRule", "NodeLintRule", "NodeTypeCheckRule"]
