"""Tests for DeadCodeRule (axm-ast dead-code integration)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from axm_audit.core.rules.dead_code import DeadCodeRule


class TestDeadCodeRule:
    """Tests for DeadCodeRule (axm-ast dead-code integration)."""

    @pytest.fixture
    def rule(self) -> DeadCodeRule:
        """Return a DeadCodeRule instance."""
        from axm_audit.core.rules.dead_code import DeadCodeRule

        return DeadCodeRule()

    def test_dead_code_rule_id_format(self, rule: DeadCodeRule) -> None:
        """Rule ID should be QUALITY_DEAD_CODE."""
        assert rule.rule_id == "QUALITY_DEAD_CODE"

    def test_dead_code_success(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 90/100 and passed=False for 2 dead symbols."""
        from axm_audit.models.results import Severity

        # axm-ast is found on PATH
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        # Mock the direct subprocess.run call for analysis
        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(
            [
                {"name": "foo", "file": "src/pkg/a.py", "line": 10, "kind": "function"},
                {"name": "bar", "file": "src/pkg/b.py", "line": 20, "kind": "class"},
            ]
        )
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 90.0  # 100 - (2 * 5)
        assert result.severity == Severity.WARNING
        assert result.details["dead_count"] == 2
        assert len(result.details["symbols"]) == 2
        assert len(result.details["top_offenders"]) == 2
        assert result.text is not None
        assert "\u2022 foo" in result.text
        assert "\u2022 bar" in result.text
        lines = result.text.strip().splitlines()
        assert len(lines) == 2

    def test_dead_code_perfect(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Score should be 100/100 and passed=True for 0 dead symbols."""
        from axm_audit.models.results import Severity

        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.passed
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert result.details["dead_count"] == 0
        assert result.details["symbols"] == []
        assert result.text is None

    def test_dead_code_skipped_not_available(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should skip gracefully if axm-ast is not on PATH."""
        from axm_audit.models.results import Severity

        # shutil.which returns None → axm-ast not found
        mocker.patch("shutil.which", return_value=None)

        result = rule.check(tmp_path)

        assert result.passed  # Graceful skip shouldn't fail the build
        assert result.details is not None
        assert result.details["score"] == 100.0
        assert result.severity == Severity.INFO
        assert "skipped" in result.details
        assert result.details["skipped"] is True
        assert "axm-ast is not available" in result.message

    def test_dead_code_json_decode_error(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should handle JSON parsing errors gracefully."""
        from axm_audit.models.results import Severity

        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "Not a JSON output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 0.0
        assert result.severity == Severity.ERROR
        assert "parse" in result.message.lower()
        assert result.text is None

    def test_dead_code_text_truncation(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """12 dead symbols should produce 10 bullets + a '+2 more' line."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": f"sym_{i}",
                "file": f"src/pkg/mod{i}.py",
                "line": i,
                "kind": "function",
            }
            for i in range(12)
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert len(lines) == 11  # 10 bullets + 1 overflow
        assert "\u2022 +2 more" in lines[-1]

    def test_dead_code_text_strips_src_prefix(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """File paths in text should have src/ prefix stripped."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": "thing",
                "file": "src/axm_audit/foo.py",
                "line": 42,
                "kind": "function",
            },
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        assert "axm_audit/foo.py" in result.text
        assert "src/axm_audit/foo.py" not in result.text

    def test_dead_code_text_module_path_fallback(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should fall back to module_path when file key is absent."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": "old_sym",
                "module_path": "pkg/legacy.py",
                "line": 5,
                "kind": "function",
            },
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        assert "\u2022 old_sym pkg/legacy.py:5" in result.text

    def test_dead_code_text_missing_file_and_module_path(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should not crash when both file and module_path are absent."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {"name": "orphan", "line": 99, "kind": "function"},
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        assert "\u2022 orphan" in result.text

    def test_dead_code_text_exactly_10_symbols(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Exactly 10 symbols should produce 10 bullets with no overflow line."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": f"sym_{i}",
                "file": f"pkg/mod{i}.py",
                "line": i,
                "kind": "function",
            }
            for i in range(10)
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert len(lines) == 10
        assert "more" not in result.text

    def test_dead_code_text_11_symbols(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """11 symbols should produce 10 bullets + '+1 more' line."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": f"sym_{i}",
                "file": f"pkg/mod{i}.py",
                "line": i,
                "kind": "function",
            }
            for i in range(11)
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert len(lines) == 11
        assert "\u2022 +1 more" in lines[-1]

    def test_dead_code_subprocess_args(
        self, rule: DeadCodeRule, mocker: MockerFixture, tmp_path: Path
    ) -> None:
        """Should call axm-ast directly with project_path as argument."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        mock_run = mocker.patch(
            "axm_audit.core.rules.dead_code.subprocess.run",
        )
        mock_result = mocker.Mock()
        mock_result.stdout = "[]"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        rule.check(tmp_path)

        mock_run.assert_called_once_with(
            ["axm-ast", "dead-code", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
