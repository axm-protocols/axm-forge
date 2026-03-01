"""Tests for ComplexityRule (radon integration)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestComplexityRule:
    """Tests for ComplexityRule (radon integration)."""

    def test_simple_functions_high_score(self, tmp_path: Path) -> None:
        """Simple functions should score high."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complex_functions_reduce_score(self, tmp_path: Path) -> None:
        """High complexity functions should reduce score."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        # Create function with CC > 10 (threshold for high complexity)
        complex_code = """
def complex_fn(x: int, y: int, z: int) -> str:
    if x > 0:
        if x > 10:
            if x > 100:
                if y > 0:
                    return "huge_pos"
                else:
                    return "huge_neg"
            elif x > 50:
                return "large"
            else:
                return "medium"
        elif x > 5:
            return "small"
        else:
            return "tiny"
    elif x < 0:
        if x < -10:
            if z > 0:
                return "neg_large_z"
            else:
                return "neg_large"
        else:
            return "neg_small"
    else:
        if y > 0 and z > 0:
            return "zero_both"
        elif y > 0:
            return "zero_y"
        return "zero"
"""
        (src / "complex.py").write_text(complex_code)

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["high_complexity_count"] > 0

    def test_rule_id_format(self) -> None:
        """Rule ID should be QUALITY_COMPLEXITY."""
        from axm_audit.core.rules.complexity import ComplexityRule

        rule = ComplexityRule()
        assert rule.rule_id == "QUALITY_COMPLEXITY"

    def test_complexity_rule_radon_in_project(self, tmp_path: Path) -> None:
        """When radon Python API is importable, use it directly."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complexity_rule_radon_fallback(self, tmp_path: Path) -> None:
        """When radon API is missing but radon binary exists, use subprocess."""
        import json as _json
        from unittest.mock import MagicMock, patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        # Simulate radon cc --json output for a simple function (CC=1)
        radon_output = _json.dumps(
            {
                str(src / "simple.py"): [
                    {
                        "type": "function",
                        "name": "add",
                        "complexity": 1,
                        "lineno": 1,
                        "col_offset": 0,
                        "endline": 2,
                    }
                ]
            }
        )

        mock_proc = MagicMock()
        mock_proc.stdout = radon_output
        mock_proc.returncode = 0

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value="/usr/bin/radon"),
            patch("subprocess.run", return_value=mock_proc),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] >= 90

    def test_complexity_rule_radon_missing_both(self, tmp_path: Path) -> None:
        """When neither API nor binary is available, return clear error."""
        from unittest.mock import patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value=None),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert not result.passed
        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        assert result.details["score"] == 0
        assert result.fix_hint is not None
        assert "uv sync" in result.fix_hint

    def test_complexity_logs_oserror(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OSError from radon subprocess is logged before returning error."""
        import logging
        from unittest.mock import patch

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )

        with (
            patch(
                "axm_audit.core.rules.complexity._try_import_radon",
                return_value=None,
            ),
            patch("shutil.which", return_value="/usr/bin/radon"),
            patch(
                "subprocess.run",
                side_effect=OSError("mocked permission denied"),
            ),
            caplog.at_level(logging.WARNING, logger="axm_audit.core.rules.complexity"),
        ):
            rule = ComplexityRule()
            result = rule.check(tmp_path)

        assert not result.passed
        assert result.details is not None
        assert result.details["score"] == 0
        assert "radon cc --json failed" in caplog.text
        assert "mocked permission denied" in caplog.text

    def test_all_offenders_shown(self, tmp_path: Path) -> None:
        """top_offenders must include ALL functions with CC >= 10, not top 5."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()

        # Generate 8 distinct complex functions (each CC >= 10)
        # Uses 3 args + boolean ops + deep nesting to ensure CC > 10
        funcs: list[str] = []
        for i in range(8):
            funcs.append(
                f"def complex_{i}(x: int, y: int, z: int) -> str:\n"
                f"    if x > 0:\n"
                f"        if x > 10:\n"
                f"            if x > 100:\n"
                f"                if y > 0:\n"
                f"                    return 'a{i}'\n"
                f"                else:\n"
                f"                    return 'b{i}'\n"
                f"            elif x > 50:\n"
                f"                return 'c{i}'\n"
                f"            else:\n"
                f"                return 'd{i}'\n"
                f"        elif x > 5:\n"
                f"            return 'e{i}'\n"
                f"        else:\n"
                f"            return 'f{i}'\n"
                f"    elif x < 0:\n"
                f"        if x < -10:\n"
                f"            if z > 0:\n"
                f"                return 'g{i}'\n"
                f"            else:\n"
                f"                return 'h{i}'\n"
                f"        else:\n"
                f"            return 'i{i}'\n"
                f"    else:\n"
                f"        if y > 0 and z > 0:\n"
                f"            return 'j{i}'\n"
                f"        elif y > 0:\n"
                f"            return 'k{i}'\n"
                f"        return 'l{i}'\n\n"
            )

        (src / "many_complex.py").write_text("\n".join(funcs))

        rule = ComplexityRule()
        result = rule.check(tmp_path)
        assert result.details is not None
        assert result.details["high_complexity_count"] == 8
        assert len(result.details["top_offenders"]) == 8
