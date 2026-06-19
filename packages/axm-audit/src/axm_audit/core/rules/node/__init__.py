"""Node/Svelte rule implementations.

These rules port the *intent* of the Python rules to the Node ecosystem
(ESLint, tsc, vitest, npm audit, …) without changing axm-audit's scoring,
categories, or ``CheckResult`` contract. They register themselves under the
``node`` / ``svelte`` frameworks via ``@register_rule(category, framework=...)``.

Importing this package fires the ``@register_rule`` decorators (side effect).
"""

from __future__ import annotations

from axm_audit.core.rules.node.lint import NodeLintRule

__all__ = ["NodeLintRule"]
