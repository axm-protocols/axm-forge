"""Split from ``test_pyproject_workspace_fallback.py``."""

import textwrap
from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_mypy, check_pyproject_ruff
from tests.integration._helpers import (
    ROOT_WORKSPACE_HEADER,
    _make_workspace,
)


class TestMemberPartialOverride:
    """Edge: member has ruff but not mypy; workspace root has both."""

    def test_ruff_from_member_mypy_from_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            select = ["E", "F"]
            per-file-ignores = { "tests/**" = ["S101"] }

            [tool.ruff.lint.isort]
            known-first-party = ["pkg"]

            [tool.mypy]
            strict = true
            pretty = true
            disallow_incomplete_defs = true
            check_untyped_defs = true
        """)
        # Member overrides ruff only (with full config), no mypy
        member_toml = textwrap.dedent("""\
            [project]
            name = "pkg"
            version = "0.1.0"

            [tool.ruff.lint]
            select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
            per-file-ignores = { "tests/**" = ["S101"] }

            [tool.ruff.lint.isort]
            known-first-party = ["pkg"]
        """)
        member = _make_workspace(tmp_path, root_toml, member_toml)

        # Ruff uses member config (which has full rules) -> pass
        ruff_result = check_pyproject_ruff(member)
        assert ruff_result.passed, (
            f"Ruff should use member config: {ruff_result.details}"
        )

        # Mypy falls back to workspace root -> pass
        mypy_result = check_pyproject_mypy(member)
        assert mypy_result.passed, (
            f"Mypy should fall back to root: {mypy_result.details}"
        )
