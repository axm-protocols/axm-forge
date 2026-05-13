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
        assert result.score == 90.0  # 100 - (2 * 5)
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
        assert result.score == 100.0
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
        assert result.score == 100.0
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
        assert result.score == 0.0
        assert result.severity == Severity.ERROR
        assert "parse" in result.message.lower()
        assert result.text is None

    @pytest.mark.parametrize(
        ("symbol_count", "expected"),
        [
            pytest.param(10, (10, None), id="exactly_10_no_overflow"),
            pytest.param(11, (11, "\u2022 +1 more"), id="11_symbols_plus_1_more"),
            pytest.param(12, (11, "\u2022 +2 more"), id="12_symbols_plus_2_more"),
        ],
    )
    def test_dead_code_text_overflow(
        self,
        rule: DeadCodeRule,
        mocker: MockerFixture,
        tmp_path: Path,
        symbol_count: int,
        expected: tuple[int, str | None],
    ) -> None:
        """Symbol list is capped at 10 bullets with optional '+N more' overflow."""
        expected_lines, overflow_marker = expected
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")

        symbols = [
            {
                "name": f"sym_{i}",
                "file": f"pkg/mod{i}.py",
                "line": i,
                "kind": "function",
            }
            for i in range(symbol_count)
        ]
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps(symbols)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        lines = result.text.strip().splitlines()
        assert len(lines) == expected_lines
        if overflow_marker is None:
            assert "more" not in result.text
        else:
            assert overflow_marker in lines[-1]

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

    @pytest.mark.parametrize(
        ("symbol", "expected_substring"),
        [
            pytest.param(
                {
                    "name": "old_sym",
                    "module_path": "pkg/legacy.py",
                    "line": 5,
                    "kind": "function",
                },
                "\u2022 old_sym pkg/legacy.py:5",
                id="module_path_fallback",
            ),
            pytest.param(
                {"name": "orphan", "line": 99, "kind": "function"},
                "\u2022 orphan",
                id="missing_file_and_module_path",
            ),
        ],
    )
    def test_dead_code_text_path_fallbacks(
        self,
        rule: DeadCodeRule,
        mocker: MockerFixture,
        tmp_path: Path,
        symbol: dict[str, object],
        expected_substring: str,
    ) -> None:
        """Text rendering handles missing file/module_path gracefully."""
        mocker.patch("shutil.which", return_value="/usr/bin/axm-ast")
        mock_run = mocker.patch("axm_audit.core.rules.dead_code.subprocess.run")
        mock_result = mocker.Mock()
        mock_result.stdout = json.dumps([symbol])
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = rule.check(tmp_path)

        assert result.text is not None
        assert expected_substring in result.text

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
