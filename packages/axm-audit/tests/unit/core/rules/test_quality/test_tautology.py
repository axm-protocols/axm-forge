"""Unit tests for TautologyRule and detect_tautologies.

Covers registry membership and per-pattern detection.
"""

from __future__ import annotations

import ast

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.tautology import detect_tautologies


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    names = {r.__name__ if isinstance(r, type) else type(r).__name__ for r in bucket}
    assert "TautologyRule" in names


@pytest.mark.parametrize(
    ("source", "expected_pattern"),
    [
        pytest.param(
            "def test_foo():\n    assert True\n",
            "trivially_true",
            id="trivially_true",
        ),
        pytest.param(
            "def test_foo():\n    x = 1\n    assert x == x\n",
            "self_compare",
            id="self_compare",
        ),
        pytest.param(
            "def test_foo():\n    r = {}\n    assert isinstance(r, dict)\n",
            "isinstance_only",
            id="isinstance_only",
        ),
        pytest.param(
            "def test_foo():\n    x = object()\n    assert x is not None\n",
            "none_check_only",
            id="none_check_only",
        ),
        pytest.param(
            "def test_foo():\n    r = []\n    assert len(r) >= 0\n",
            "len_tautology",
            id="len_tautology",
        ),
        pytest.param(
            "def test_foo():\n    assert True == True\n",
            "trivially_true",
            id="priority_trivial_beats_self_compare",
        ),
        pytest.param(
            "def test_foo():\n    x = 1\n    self.assertEqual(x, x)\n",
            "self_compare",
            id="unittest_assert_equal_self_compare",
        ),
        pytest.param(
            "def test_foo():\n    assert 100 - 5 * 2 == 90\n",
            "constant_arithmetic",
            id="constant_arithmetic_subtract_multiply",
        ),
        pytest.param(
            "def test_foo():\n    assert 100 - 50 * 2 == 0\n",
            "constant_arithmetic",
            id="constant_arithmetic_zero_result",
        ),
        pytest.param(
            "def test_foo():\n    assert int(0.90 * 100) == 90\n",
            "constant_arithmetic",
            id="constant_arithmetic_with_int_call",
        ),
        pytest.param(
            "def test_foo():\n    assert 1\n",
            "trivially_true",
            id="bare_constant_stays_trivially_true",
        ),
    ],
)
def test_detect_single_pattern(source: str, expected_pattern: str) -> None:
    tree = _parse(source)
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == expected_pattern


def test_detect_mock_echo() -> None:
    tree = _parse(
        "def test_foo(mocker):\n"
        "    m = mocker.MagicMock()\n"
        "    m.do.return_value = 42\n"
        "    assert m.do() == 42\n"
    )
    findings = detect_tautologies(tree, path="test_foo.py")
    assert any(f.pattern == "mock_echo" for f in findings)


def test_constant_arithmetic_skips_when_var_present() -> None:
    tree = _parse("def test_foo():\n    x = 1\n    assert x == 5 - 2 + 7\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert findings == []
