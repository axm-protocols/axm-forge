"""AXM CLI — Thin autodiscovery wrapper.

Discovers and exposes commands from installed AXM packages
via the ``axm.commands`` entry-point group.

Each package declares commands in its ``pyproject.toml``::

    [project.entry-points."axm.commands"]
    init = "axm_init.cli:init"
    check = "axm_init.cli:check"

Then ``pip install axm axm-init`` → ``axm init``, ``axm check``.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any

import cyclopts

__all__ = ["create_app", "main"]

logger = logging.getLogger(__name__)

_EP_GROUP = "axm.commands"


def create_app() -> cyclopts.App:
    """Create the AXM CLI application with autodiscovered commands.

    Returns:
        Configured cyclopts App with all discovered commands registered.
    """
    app = cyclopts.App(
        name="axm",
        help="AXM — Protocol execution ecosystem.",
        version_flags=[],
    )

    # Auto-discover commands from installed packages
    discovered = 0
    for ep in importlib.metadata.entry_points(group=_EP_GROUP):
        try:
            command_fn: Any = ep.load()
            app.command(command_fn, name=ep.name)
            discovered += 1
            logger.debug("Discovered command: %s (from %s)", ep.name, ep.dist)
        except Exception:
            logger.warning(
                "Failed to load command '%s' from entry point",
                ep.name,
                exc_info=True,
            )

    if discovered == 0:

        @app.default
        def _no_commands() -> None:
            """No commands available. Install AXM packages to add commands.

            Examples:
                pip install axm[init]     # adds: axm init, axm check
                pip install axm[audit]    # adds: axm audit
                pip install axm[all]      # adds all commands
            """
            import sys

            sys.stderr.write(
                "No commands available.\n\n"
                "Install AXM packages to add commands:\n"
                "  pip install axm[init]   → axm init, axm check\n"
                "  pip install axm[audit]  → axm audit\n"
                "  pip install axm[all]    → all commands\n"
            )
            sys.exit(1)

    return app


app = create_app()


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
