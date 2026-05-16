"""Split from ``test_pyproject_workspace_fallback.py``."""

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_init.checks.pyproject import (
    check_pyproject_coverage,
    check_pyproject_mypy,
    check_pyproject_pytest,
    check_pyproject_ruff,
    check_pyproject_ruff_rules,
)
from tests.integration._helpers import (
    ROOT_WORKSPACE_HEADER,
    _make_workspace,
)

_PYTEST_SECTION = textwrap.dedent("""\

    [tool.pytest.ini_options]
    addopts = ["--strict-markers", "--strict-config", "--import-mode=importlib"]
    pythonpath = ["src"]
    filterwarnings = ["error"]
""")

_RUFF_SECTION = textwrap.dedent("""\

    [tool.ruff.lint]
    per-file-ignores = { "tests/**" = ["S101"] }

    [tool.ruff.lint.isort]
    known-first-party = ["pkg"]
""")

_COVERAGE_SECTION = textwrap.dedent("""\

    [tool.coverage.run]
    branch = true
    relative_files = true

    [tool.coverage.xml]
    output = "coverage.xml"

    [tool.coverage.report]
    exclude_lines = ["pragma: no cover"]
""")

_MYPY_SECTION = textwrap.dedent("""\

    [tool.mypy]
    strict = true
    pretty = true
    disallow_incomplete_defs = true
    check_untyped_defs = true
""")


# ---------------------------------------------------------------------------
# Unit tests from test_spec
# ---------------------------------------------------------------------------


_RUFF_RULES_SECTION = textwrap.dedent("""\

    [tool.ruff.lint]
    select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
""")


class TestCheckPassesWhenConfigInWorkspaceRoot:
    """Each tooling check resolves config from the workspace root."""

    @pytest.mark.parametrize(
        ("section", "checker"),
        [
            pytest.param(
                _RUFF_RULES_SECTION, check_pyproject_ruff_rules, id="ruff_rules"
            ),
            pytest.param(_MYPY_SECTION, check_pyproject_mypy, id="mypy"),
            pytest.param(_PYTEST_SECTION, check_pyproject_pytest, id="pytest"),
            pytest.param(_COVERAGE_SECTION, check_pyproject_coverage, id="coverage"),
            pytest.param(_RUFF_SECTION, check_pyproject_ruff, id="ruff"),
        ],
    )
    def test_passes_when_section_in_workspace_root(
        self, tmp_path: Path, section: str, checker: Any
    ) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + section
        member = _make_workspace(tmp_path, root_toml)
        result = checker(member)
        assert result.passed, f"Expected pass, got: {result.details}"
