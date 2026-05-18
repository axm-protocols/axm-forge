"""Integration tests for the complexity-rule basename collision fix.

Two source files that share a basename and both define a function with
the same name must not collide in the cognitive-complexity map. The fix
uses ``(POSIX path relative to src_path, function_name)`` as the key,
so both writers and readers must agree on that shape — verified through
the public ``ComplexityRule.check`` surface.
"""

from __future__ import annotations

import logging
import shutil
import tomllib
from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock, patch

import pytest

from axm_audit.core.rules.complexity import ComplexityRule

pytestmark = pytest.mark.integration


# Flat fan-out: high cyclomatic (>=11), low cognitive (depth 1 each).
FOO_FLAT = """\
def foo(x):
    if x == 0: return 0
    if x == 1: return 1
    if x == 2: return 2
    if x == 3: return 3
    if x == 4: return 4
    if x == 5: return 5
    if x == 6: return 6
    if x == 7: return 7
    if x == 8: return 8
    if x == 9: return 9
    if x == 10: return 10
    if x == 11: return 11
    return -1
"""

# Deeply nested: moderate cyclomatic, very high cognitive (>15).
FOO_NESTED = """\
def foo(x):
    if x > 0:
        if x > 1:
            if x > 2:
                if x > 3:
                    if x > 4:
                        if x > 5:
                            if x > 6:
                                return 1
    return 0
"""


def _build_collision_tree(root: Path) -> Path:
    """Create ``src/a/utils.py`` and ``src/b/utils.py`` both defining ``foo``."""
    src = root / "src"
    (src / "a").mkdir(parents=True)
    (src / "b").mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "a" / "__init__.py").write_text("", encoding="utf-8")
    (src / "b" / "__init__.py").write_text("", encoding="utf-8")
    (src / "a" / "utils.py").write_text(FOO_FLAT, encoding="utf-8")
    (src / "b" / "utils.py").write_text(FOO_NESTED, encoding="utf-8")
    return src


def _foo_offenders(result_details: dict[str, object]) -> list[dict[str, object]]:
    """Return all ``foo`` entries from a ComplexityRule.check details payload."""
    offenders = result_details["top_offenders"]
    return [o for o in offenders if o["function"] == "foo"]


def test_check_assigns_distinct_cognitive_per_file(tmp_path):
    """AC1+AC2+AC4: same-basename ``foo`` keeps a per-file cognitive score.

    Drives the public ``ComplexityRule.check`` API end-to-end. If the cog
    map ever collapses both ``foo`` entries onto a single basename key, the
    two cognitive values would coincide and this test would fail.
    """
    pytest.importorskip("complexipy")
    _build_collision_tree(tmp_path)

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    foos = _foo_offenders(result.details)
    assert len(foos) >= 2, (
        f"expected both foo offenders, got {result.details['top_offenders']}"
    )
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert len(set(cogs_by_file.values())) == 2, (
        f"expected distinct cognitive per file, got {cogs_by_file}"
    )
    assert all(cog > 0 for cog in cogs_by_file.values()), (
        f"cognitive map collapsed to zero for one file: {cogs_by_file}"
    )


def test_check_via_subprocess_assigns_distinct_cognitive_per_file(tmp_path, mocker):
    """AC3: the subprocess radon path looks cog_map up via relative POSIX key."""
    pytest.importorskip("complexipy")
    if shutil.which("radon") is None:
        pytest.skip("radon binary not available")
    _build_collision_tree(tmp_path)

    # Force the radon subprocess branch by pretending the API is missing.
    mocker.patch(
        "axm_audit.core.rules.complexity._try_import_radon",
        return_value=None,
    )

    result = ComplexityRule().check(tmp_path)

    assert result.details is not None
    foos = _foo_offenders(result.details)
    assert len(foos) >= 2, (
        f"expected both foo offenders, got {result.details['top_offenders']}"
    )
    cogs_by_file = {o["file"]: o["cognitive"] for o in foos}
    assert len(set(cogs_by_file.values())) == 2, (
        f"expected distinct cognitive per file, got {cogs_by_file}"
    )


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


def _rank_for(cc: int) -> str:
    """Mirror radon's grade mapping.

    A 1-5, B 6-10, C 11-20, D 21-30, E 31-40, F 41+.
    """
    if cc <= 5:
        return "A"
    if cc <= 10:
        return "B"
    if cc <= 20:
        return "C"
    if cc <= 30:
        return "D"
    if cc <= 40:
        return "E"
    return "F"


def _make_offenders(
    items: list[tuple[str, str, int]],
) -> list[dict[str, str | int]]:
    """Build offender dicts from (file, function, cc) tuples (cog=0, reason='cc')."""
    return [
        {
            "file": f,
            "function": fn,
            "cc": cc,
            "rank": _rank_for(cc),
            "cognitive": 0,
            "reason": "cc",
        }
        for f, fn, cc in items
    ]


class TestComplexityCheckTextRendering:
    """Functional: text lines from check() contain file:function pattern."""

    def test_complexity_check_text_rendering(
        self, rule: ComplexityRule, tmp_path: object
    ) -> None:
        """Simulate _build_result via direct call with realistic data."""
        offenders = _make_offenders(
            [
                ("src/engine.py", "run_pipeline", 22),
                ("src/parser.py", "parse_tokens", 18),
                ("src/validator.py", "validate_all", 14),
            ]
        )
        result = rule._build_result(offenders)

        assert result.text is not None
        for line in result.text.split("\n"):
            assert ":" in line
            assert "→" not in line
            assert "cc=" in line


class _ProjectBuilder(Protocol):
    def __call__(self, name: str, n_branches: int) -> Path: ...


def _make_function_with_cc(name: str, n_branches: int) -> str:
    """Build a Python function with cyclomatic complexity == ``n_branches`` + 1."""
    lines = [f"def {name}(x):"]
    for i in range(n_branches):
        lines.append(f"    if x == {i}:")
        lines.append("        return 0")
    lines.append("    return 1")
    return "\n".join(lines) + "\n"


@pytest.fixture
def project_with_function(tmp_path: Path) -> _ProjectBuilder:
    def _build(name: str, n_branches: int) -> Path:
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        module = src / f"{name}.py"
        module.write_text(_make_function_with_cc(name, n_branches), encoding="utf-8")
        return tmp_path

    return _build


def test_cc_equals_10_grade_b_passes(
    project_with_function: _ProjectBuilder,
) -> None:
    """AC1: CC=10 (grade B) must NOT count as a high-complexity violation."""
    project = project_with_function("mod_b", n_branches=9)

    rule = ComplexityRule()
    result = rule.check(project)

    assert result.details is not None
    assert result.details["high_complexity_count"] == 0


def test_cc_equals_11_grade_c_flagged(
    project_with_function: _ProjectBuilder,
) -> None:
    """AC2: CC=11 (grade C) must count as a violation with rank='C'."""
    project = project_with_function("mod_c", n_branches=10)

    rule = ComplexityRule()
    result = rule.check(project)

    assert result.details is not None
    assert result.details["high_complexity_count"] == 1
    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "C"


def test_high_grade_d_includes_rank(
    project_with_function: _ProjectBuilder,
) -> None:
    """AC3, AC5: a CC>=21 function reports rank='D' in offenders."""
    project = project_with_function("mod_d", n_branches=24)

    rule = ComplexityRule()
    result = rule.check(project)

    assert result.details is not None
    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "D"
    assert offenders[0]["cc"] >= 21


def test_top_offenders_have_rank_key(tmp_path: Path) -> None:
    """AC5: every offender entry exposes a 'rank' key alongside 'cc'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text(_make_function_with_cc("a", 11), encoding="utf-8")
    (src / "b.py").write_text(_make_function_with_cc("b", 14), encoding="utf-8")

    rule = ComplexityRule()
    result = rule.check(tmp_path)

    assert result.details is not None
    offenders = result.details["top_offenders"]
    assert len(offenders) == 2
    assert all("rank" in o for o in offenders)
    assert all("cc" in o for o in offenders)


_HIGH_CC_LOW_COG_CASES = "\n".join(
    f"        case {i}: return {i}" for i in range(1, 13)
)
_HIGH_CC_LOW_COG_BODY = (
    f"def big_match(x):\n    match x:\n{_HIGH_CC_LOW_COG_CASES}\n"
    f"        case _: return -1\n"
)


_LOW_CC_HIGH_COG_BODY = (
    "def deeply_nested(items, flag):\n"
    "    for a in items:\n"
    "        if flag:\n"
    "            for b in a:\n"
    "                if b:\n"
    "                    for c in b:\n"
    "                        if c:\n"
    "                            return c\n"
    "    return None\n"
)

_BOTH_THRESHOLDS_BODY = (
    "def both(items, a, b, c, d, e):\n"
    "    for x in items:\n"
    "        if a:\n"
    "            for y in x:\n"
    "                if b:\n"
    "                    for z in y:\n"
    "                        if c:\n"
    "                            if d:\n"
    "                                if e:\n"
    "                                    return z\n"
    "                        elif a and b:\n"
    "                            return y\n"
    "                elif c and d:\n"
    "                    return x\n"
    "        elif b or c:\n"
    "            return a\n"
    "    return None\n"
)


@pytest.fixture
def rule_from_unit() -> ComplexityRule:
    return ComplexityRule()


def _write_from_unit(tmp_path: Path, body: str) -> Path:
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    module = src / "m.py"
    module.write_text(body, encoding="utf-8")
    return tmp_path


class TestComplexityRuleIO:
    """Tests for ComplexityRule (radon integration)."""

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
        assert result.score is not None
        assert result.score >= 90

    def test_complexity_rule_radon_fallback(self, tmp_path: Path) -> None:
        """When radon API is missing but radon binary exists, use subprocess."""
        import json as _json

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
        assert result.score is not None
        assert result.score >= 90

    def test_complexity_rule_radon_missing_both(self, tmp_path: Path) -> None:
        """When neither API nor binary is available, return clear error."""

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
        assert result.score == 0
        assert result.fix_hint is not None
        assert "uv sync" in result.fix_hint

    def test_complexity_logs_oserror(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OSError from radon subprocess is logged before returning error."""
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
        assert result.score == 0
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

    def test_complexity_qualifies_method_names(self, tmp_path: Path) -> None:
        """Methods should be reported as ClassName.method, not just method."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()

        # Two classes each with a check() method — one exceeds CC threshold
        code = """\
class LowClass:
    def check(self, x: int) -> str:
        return "ok"

class HighClass:
    def check(self, x: int, y: int, z: int) -> str:
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
        (src / "multi_class.py").write_text(code)

        rule = ComplexityRule()
        result = rule.check(tmp_path)

        assert result.details is not None
        offenders = result.details["top_offenders"]
        assert len(offenders) >= 1
        names = [o["function"] for o in offenders]
        assert "HighClass.check" in names
        # Must NOT have bare "check" — always qualified
        assert "check" not in names

    def test_complexity_toplevel_unqualified(self, tmp_path: Path) -> None:
        """Top-level functions should remain unqualified (no class prefix)."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()

        code = """\
def my_func(x: int, y: int, z: int) -> str:
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
        (src / "toplevel.py").write_text(code)

        rule = ComplexityRule()
        result = rule.check(tmp_path)

        assert result.details is not None
        offenders = result.details["top_offenders"]
        assert len(offenders) >= 1
        names = [o["function"] for o in offenders]
        assert "my_func" in names
        # No dot means no class prefix
        assert all("." not in n for n in names)

    def test_complexity_subprocess_qualifies_method_names(self, tmp_path: Path) -> None:
        """Subprocess fallback should also qualify method names."""
        import json as _json

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "dummy.py").write_text("pass\n")

        # Simulate radon cc --json output with classname field
        radon_output = _json.dumps(
            {
                str(src / "dummy.py"): [
                    {
                        "type": "method",
                        "name": "check",
                        "classname": "HighClass",
                        "complexity": 12,
                        "rank": "C",
                        "lineno": 1,
                        "col_offset": 4,
                        "endline": 30,
                    },
                    {
                        "type": "function",
                        "name": "top_func",
                        "classname": "",
                        "complexity": 15,
                        "rank": "C",
                        "lineno": 32,
                        "col_offset": 0,
                        "endline": 60,
                    },
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

        assert result.details is not None
        offenders = result.details["top_offenders"]
        names = [o["function"] for o in offenders]
        assert "HighClass.check" in names
        assert "top_func" in names
        # No bare "check"
        assert "check" not in names

    def test_type_alias_doesnt_crash(self, tmp_path: Path) -> None:
        """Projects using ``type X = ...`` syntax pass without crash (API path)."""
        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "from __future__ import annotations\n\n"
            "type Foo = int | str\n\n"
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )

        rule = ComplexityRule()
        result = rule.check(tmp_path)

        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.details is not None
        # Must not crash — score should be valid
        assert isinstance(result.score, int)
        assert result.score >= 0

    def test_type_alias_subprocess_fallback(self, tmp_path: Path) -> None:
        """Subprocess path skips string entries produced by radon for type aliases."""
        import json as _json

        from axm_audit.core.rules.complexity import ComplexityRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("pass\n")

        # radon cc --json produces a bare string for type aliases
        radon_output = _json.dumps(
            {
                str(src / "mod.py"): [
                    "type Foo = int | str",
                    {
                        "type": "function",
                        "name": "add",
                        "complexity": 1,
                        "lineno": 4,
                        "col_offset": 0,
                        "endline": 5,
                    },
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

        assert result.rule_id == "QUALITY_COMPLEXITY"
        assert result.passed
        assert result.details is not None
        assert isinstance(result.score, int)
        assert result.score >= 90

    def test_process_radon_output_helper(self, tmp_path: Path) -> None:
        """Tests that _process_radon_output correctly extracts metrics."""
        from axm_audit.core.rules.complexity import ComplexityRule

        data: dict[str, list[dict[str, object]]] = {
            "file1.py": [
                {
                    "type": "function",
                    "name": "simple",
                    "classname": "",
                    "complexity": 2,
                    "rank": "A",
                },
                {
                    "type": "method",
                    "name": "complex_method",
                    "classname": "MyClass",
                    "complexity": 15,
                    "rank": "C",
                },
            ],
            "file2.py": [
                {
                    "type": "function",
                    "name": "another_complex",
                    "classname": "",
                    "complexity": 20,
                    "rank": "C",
                },
                "ignore_this_string_block",  # type: ignore[list-item]
            ],
        }

        rule = ComplexityRule()
        result = rule._process_radon_output(data)

        assert result.passed is False
        assert result.details is not None
        assert result.details["high_complexity_count"] == 2
        assert result.score == 80

        offenders = result.details["top_offenders"]
        assert len(offenders) == 2
        assert offenders[0]["function"] == "another_complex"
        assert offenders[0]["cc"] == 20
        assert offenders[1]["function"] == "MyClass.complex_method"
        assert offenders[1]["cc"] == 15


def test_complexipy_dep_declared_from_unit() -> None:
    pkg_root = Path(__file__).resolve().parents[2]
    pyproject = pkg_root / "pyproject.toml"
    cfg = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = cfg["project"]["dependencies"]
    assert any(d.startswith("complexipy") for d in deps), deps


@pytest.mark.parametrize(
    ("body", "expected_reason"),
    [
        pytest.param(
            _LOW_CC_HIGH_COG_BODY, "cog", id="low_cc_high_cognitive_flagged_from_unit"
        ),
        pytest.param(
            _HIGH_CC_LOW_COG_BODY,
            "cc",
            id="high_cc_low_cognitive_flagged_as_cc_from_unit",
        ),
        pytest.param(
            _BOTH_THRESHOLDS_BODY,
            "cc+cog",
            id="both_thresholds_single_violation_from_unit",
        ),
    ],
)
def test_complexity_offender_reason_from_unit(
    tmp_path: Path,
    rule_from_unit: ComplexityRule,
    body: str,
    expected_reason: str,
) -> None:
    project = _write_from_unit(tmp_path, body)
    result = rule_from_unit.check(project)
    assert result.details is not None
    assert result.details["high_complexity_count"] == 1
    top = result.details["top_offenders"][0]
    assert top["reason"] == expected_reason


def test_offenders_sorted_by_max_metric_from_unit(
    tmp_path: Path, rule_from_unit: ComplexityRule
) -> None:
    func_a_cases = "\n".join(f"        case {i}: return {i}" for i in range(1, 14))
    func_a = (
        f"def func_a(x):\n    match x:\n{func_a_cases}\n        case _: return -1\n"
    )
    func_b = (
        "def func_b(items):\n"
        "    for i in items:\n"
        "        if i:\n"
        "            for j in i:\n"
        "                if j:\n"
        "                    for k in j:\n"
        "                        if k:\n"
        "                            for ll in k:\n"
        "                                if ll:\n"
        "                                    for m in ll:\n"
        "                                        if m:\n"
        "                                            return m\n"
        "    return None\n"
    )
    project = _write_from_unit(tmp_path, func_a + "\n\n" + func_b)
    result = rule_from_unit.check(project)
    assert result.details is not None
    offenders = result.details["top_offenders"]
    assert len(offenders) == 2
    assert offenders[0]["function"] == "func_b"


def test_offender_dict_has_cognitive_key_from_unit(
    tmp_path: Path, rule_from_unit: ComplexityRule
) -> None:
    cases = "\n".join(f"        case {i}: return {i}" for i in range(1, 16))
    body = f"def cc_only(x):\n    match x:\n{cases}\n        case _: return -1\n"
    project = _write_from_unit(tmp_path, body)
    result = rule_from_unit.check(project)
    assert result.details is not None
    top = result.details["top_offenders"][0]
    assert "cognitive" in top
    assert top["cognitive"] == 0


def _function_cc11(name: str) -> str:
    """Build a function with cyclomatic complexity == 11 (grade C)."""
    lines = [f"def {name}(x):"]
    for i in range(10):
        lines.append(f"    if x == {i}:")
        lines.append("        return 0")
    lines.append("    return 1")
    return "\n".join(lines) + "\n"


def test_subprocess_path_uses_grade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC2: subprocess radon path flags CC=11 with rank='C'."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text(_function_cc11("feature"), encoding="utf-8")

    monkeypatch.setattr(
        "axm_audit.core.rules.complexity._try_import_radon",
        lambda: None,
    )
    monkeypatch.chdir(tmp_path)

    rule = ComplexityRule()
    result = rule.check(tmp_path)

    assert result.details is not None
    assert result.details["high_complexity_count"] == 1
    offenders = result.details["top_offenders"]
    assert offenders[0]["rank"] == "C"
