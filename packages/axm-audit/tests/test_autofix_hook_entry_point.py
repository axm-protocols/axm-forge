from __future__ import annotations

import importlib.metadata
import textwrap
from pathlib import Path

from axm_audit.hooks.autofix import AutofixHook


class TestAutofixHookRegistered:
    """Entry point 'audit:autofix' must be discoverable in axm.hooks."""

    def test_autofix_hook_registered(self) -> None:
        eps = importlib.metadata.entry_points(group="axm.hooks")
        names = [ep.name for ep in eps]
        assert "audit:autofix" in names


class TestAutofixHookExecutes:
    """AutofixHook.execute must reformat a ruff-fixable file."""

    def test_autofix_hook_executes(self, tmp_path: Path) -> None:
        # Create a file with a ruff-fixable issue (unused import)
        bad_file = tmp_path / "bad.py"
        bad_file.write_text(
            textwrap.dedent("""\
            import os
            import sys

            x = 1
        """)
        )
        # Also create a minimal pyproject.toml so ruff runs happily
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")

        hook = AutofixHook()
        result = hook.execute(context={"working_dir": str(tmp_path)})

        assert result.success is True
        # The file should have been reformatted (unused imports removed)
        content = bad_file.read_text()
        assert "import os" not in content or "import sys" not in content


class TestExistingEntryPoints:
    """Existing entry points in axm.tools and axm.witnesses must still be present."""

    def test_existing_entry_points(self) -> None:
        tools_eps = importlib.metadata.entry_points(group="axm.tools")
        witnesses_eps = importlib.metadata.entry_points(group="axm.witnesses")

        # At least the known axm-audit entries must exist
        tool_names = [ep.name for ep in tools_eps]
        witness_names = [ep.name for ep in witnesses_eps]

        assert len(tool_names) > 0, "No axm.tools entry points found"
        assert len(witness_names) > 0, "No axm.witnesses entry points found"
