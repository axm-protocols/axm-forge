"""Svelte-specific gold-standard checks (the svelte delta over the node base).

Discovered by ``CheckEngine`` only when the project's framework is ``svelte``,
on top of the shared node checks (see ``resolve_frameworks``). Mirrors the
audit-side ``rules/svelte/`` delta.
"""

from __future__ import annotations
