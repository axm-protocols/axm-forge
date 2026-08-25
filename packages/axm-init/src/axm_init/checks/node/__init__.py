"""Node/Svelte gold-standard checks.

Port of the Python gold-standard checks' *intent* to the Node ecosystem
(``package.json`` instead of ``pyproject.toml``, ``tsconfig.json`` /
``svelte.config.js`` instead of ruff/mypy config, …). Discovered by
``CheckEngine`` when the project's framework is ``node`` or ``svelte``.

Each public ``check_*`` function keeps the Python checker's signature
(``(Path) -> CheckResult``), so the engine, scoring, and report formatting are
framework-agnostic.
"""

from __future__ import annotations
