"""Integration: AutofixHook end-to-end against real filesystem + ruff subprocess."""

from __future__ import annotations

import textwrap
from pathlib import Path

from axm_audit.hooks.autofix import AutofixHook


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
