"""Svelte-specific rule delta (sits on top of the shared ``node`` base layer).

A Svelte project runs every ``node`` rule (via ``resolve_frameworks``) PLUS the
rules here. The svelte delta is small by design: the research shows Svelte puts
its UI concerns in the *compiler* (a11y warnings, type-checking ``.svelte``)
rather than in ESLint plugins, so the delta is essentially one extra CLI —
``svelte-check`` — that ``tsc`` alone cannot replace.

Importing this package fires the ``@register_rule`` decorators (side effect).
"""

from __future__ import annotations

from axm_audit.core.rules.svelte.svelte_check import SvelteCheckRule

__all__ = ["SvelteCheckRule"]
