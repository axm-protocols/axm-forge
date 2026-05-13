"""Functional tests for CLI — end-to-end flows.

TestScaffoldFlow uses a shared ``scope="module"`` fixture that scaffolds once
via the real Copier adapter, then all tests assert read-only against the same
output.  Each test is marked ``@pytest.mark.slow`` so it can be excluded from
the default fast run.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from axm_init.cli import app


def _run(args: list[str]) -> tuple[str, int]:
    """Run CLI and capture stdout + exit code."""
    f = io.StringIO()
    code = 0
    try:
        with redirect_stdout(f):
            app(args, exit_on_error=False)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
    return f.getvalue(), code


class TestVersionFlow:
    """End-to-end test for version command."""

    def test_version_returns_valid_output(self) -> None:
        """version command produces clean output."""
        output, code = _run(["version"])
        assert code == 0
        output = output.strip()
        assert output.startswith("axm-init ")
        # Should not contain error messages
        assert "Error" not in output
        assert "Traceback" not in output
