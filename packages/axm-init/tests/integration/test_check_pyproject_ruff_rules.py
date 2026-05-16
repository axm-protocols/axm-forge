"""Split from ``test_pyproject_gold_standard_requirements.py``."""

import textwrap
from pathlib import Path

from axm_init.checks.pyproject import check_pyproject_ruff_rules
from tests.integration._helpers import (
    ROOT_WORKSPACE_HEADER,
    _make_workspace,
)


class TestCheckPyprojectRuffRules:
    def test_pass(self, gold_project: Path) -> None:
        r = check_pyproject_ruff_rules(gold_project)
        assert r.passed is True
        assert r.weight == 2

    def test_fail_no_select(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\n')
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False

    def test_fail_missing_new_rules(self, tmp_path: Path) -> None:
        """Old 5-rule set should now fail — missing S, BLE, PLR, N."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "S" in missing
        assert "BLE" in missing
        assert "PLR" in missing
        assert "N" in missing

    def test_pass_with_all(self, tmp_path: Path) -> None:
        """select = ['ALL'] includes everything — should pass."""
        toml = '[project]\nname="x"\n[tool.ruff.lint]\nselect = ["ALL"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_pass_with_extend_select(self, tmp_path: Path) -> None:
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "S"]\n'
            'extend-select = ["I", "UP", "B", "BLE", "PLR", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is True

    def test_fail_subset_of_new_rules(self, tmp_path: Path) -> None:
        """Only S and N added — should fail listing BLE, PLR."""
        toml = (
            '[project]\nname="x"\n[tool.ruff.lint]\n'
            'select = ["E", "F", "I", "UP", "B", "S", "N"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        r = check_pyproject_ruff_rules(tmp_path)
        assert r.passed is False
        missing = str(r.details)
        assert "BLE" in missing
        assert "PLR" in missing
        # S and N should NOT be in missing
        # (they're in the details string as context, check the sorted list)
        assert r.message == "Missing 2 essential ruff rule(s)"


class TestMemberOverrideWins:
    """test_member_override_wins: member config takes precedence over workspace root."""

    def test_member_ruff_overrides_root(self, tmp_path: Path) -> None:
        root_toml = ROOT_WORKSPACE_HEADER + textwrap.dedent("""\

            [tool.ruff.lint]
            select = ["E", "F"]
        """)
        # Member defines its own ruff rules that include all required
        member_toml = textwrap.dedent("""\
            [project]
            name = "pkg"
            version = "0.1.0"

            [tool.ruff.lint]
            select = ["E", "F", "I", "UP", "B", "S", "BLE", "PLR", "N"]
        """)
        member = _make_workspace(tmp_path, root_toml, member_toml)
        result = check_pyproject_ruff_rules(member)
        assert result.passed, f"Member override should win, got: {result.details}"
