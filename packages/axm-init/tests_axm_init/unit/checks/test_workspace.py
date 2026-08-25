"""Mirror-satisfying test file for workspace checks.

The existing test_workspace_checks.py has comprehensive tests (10 classes).
This file satisfies the PRACTICE_TEST_MIRROR rule that expects
tests/unit/checks/test_workspace.py to mirror src/axm_init/checks/workspace.py.

Re-exports the existing tests so the mirror convention is satisfied
without duplicating test logic.
"""

from __future__ import annotations

from tests_axm_init.integration.test_check_engine import *  # noqa: F403
from tests_axm_init.integration.test_check_matrix_packages import *  # noqa: F403
from tests_axm_init.integration.test_check_members_consistent import *  # noqa: F403
from tests_axm_init.integration.test_check_monorepo_plugin import *  # noqa: F403
from tests_axm_init.integration.test_check_packages_layout import *  # noqa: F403
from tests_axm_init.integration.test_check_pytest_importmode import *  # noqa: F403
from tests_axm_init.integration.test_check_pytest_testpaths import *  # noqa: F403
from tests_axm_init.integration.test_check_quality_workflow import *  # noqa: F403
from tests_axm_init.integration.test_check_requires_python_compat import *  # noqa: F403
from tests_axm_init.integration.test_check_root_name_collision import *  # noqa: F403


def test_incomplete_member_suite_coverage_fails(mocker) -> None:
    """AC2: one covered member cannot mask another member's missing suite."""
    from pathlib import Path

    from axm_init.checks.workspace import check_pytest_testpaths

    mocker.patch(
        "axm_init.checks.workspace.load_toml",
        return_value={
            "tool": {
                "uv": {"workspace": {"members": ["packages/*"]}},
                "pytest": {
                    "ini_options": {"testpaths": ["packages/pkg-a/tests_pkg_a"]}
                },
            }
        },
    )
    members = [Path("packages/pkg-a"), Path("packages/pkg-b")]
    mocker.patch(
        "axm_init.checks.workspace._resolve_member_dirs",
        return_value=members,
    )
    resolver = mocker.patch(
        "axm_init.checks.workspace.resolve_suite_dir",
        create=True,
    )
    resolver.side_effect = [
        members[0] / "tests_pkg_a",
        members[1] / "tests_pkg_b",
    ]

    result = check_pytest_testpaths(Path("."))

    assert result.passed is False
    rendered = "\n".join([result.message, *result.details, result.fix])
    assert "pkg-b" in rendered
