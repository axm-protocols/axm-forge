"""Mirror-satisfying test file for workspace checks.

The existing test_workspace_checks.py has comprehensive tests (10 classes).
This file satisfies the PRACTICE_TEST_MIRROR rule that expects
tests/unit/checks/test_workspace.py to mirror src/axm_init/checks/workspace.py.

Re-exports the existing tests so the mirror convention is satisfied
without duplicating test logic.
"""

from __future__ import annotations

from tests.unit.checks.test_workspace_checks import *  # noqa: F403
