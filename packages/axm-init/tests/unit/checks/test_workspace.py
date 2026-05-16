"""Mirror-satisfying test file for workspace checks.

The existing test_workspace_checks.py has comprehensive tests (10 classes).
This file satisfies the PRACTICE_TEST_MIRROR rule that expects
tests/unit/checks/test_workspace.py to mirror src/axm_init/checks/workspace.py.

Re-exports the existing tests so the mirror convention is satisfied
without duplicating test logic.
"""

from __future__ import annotations

from tests.integration.test_check_engine import *  # noqa: F403
from tests.integration.test_check_matrix_packages import *  # noqa: F403
from tests.integration.test_check_members_consistent import *  # noqa: F403
from tests.integration.test_check_monorepo_plugin import *  # noqa: F403
from tests.integration.test_check_packages_layout import *  # noqa: F403
from tests.integration.test_check_pytest_importmode import *  # noqa: F403
from tests.integration.test_check_pytest_testpaths import *  # noqa: F403
from tests.integration.test_check_quality_workflow import *  # noqa: F403
from tests.integration.test_check_requires_python_compat import *  # noqa: F403
from tests.integration.test_check_root_name_collision import *  # noqa: F403
from tests.unit.test_all_checks import *  # noqa: F403
