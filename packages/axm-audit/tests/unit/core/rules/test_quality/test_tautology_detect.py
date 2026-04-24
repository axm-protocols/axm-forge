from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.rules.registry import get_registry
from axm_audit.core.rules.test_quality.tautology import (
    TautologyRule,
    detect_tautologies,
)
from axm_audit.core.severity import Severity


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_rule_registered() -> None:
    registry = get_registry()
    bucket = registry.get("test_quality", [])
    names = {r.__name__ if isinstance(r, type) else type(r).__name__ for r in bucket}
    assert "TautologyRule" in names


def test_detect_trivially_true() -> None:
    tree = _parse("def test_foo():\n    assert True\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == "trivially_true"


def test_detect_self_compare() -> None:
    tree = _parse("def test_foo():\n    x = 1\n    assert x == x\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == "self_compare"


def test_detect_isinstance_only() -> None:
    tree = _parse("def test_foo():\n    r = {}\n    assert isinstance(r, dict)\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == "isinstance_only"


def test_detect_none_check_only() -> None:
    tree = _parse("def test_foo():\n    x = object()\n    assert x is not None\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == "none_check_only"


def test_detect_len_tautology() -> None:
    tree = _parse("def test_foo():\n    r = []\n    assert len(r) >= 0\n")
    findings = detect_tautologies(tree, path="test_foo.py")
    assert len(findings) == 1
    assert findings[0].pattern == "len_tautology"


def test_detect_mock_echo() -> None:
    tree = _parse(
        "def test_foo(mocker):\n"
        "    m = mocker.MagicMock()\n"
        "    m.do.return_value = 42\n"
        "    assert m.do() == 42\n"
    )
    findings = detect_tautologies(tree, path="test_foo.py")
    assert any(f.pattern == "mock_echo" for f in findings)


def test_severity_warning(tmp_path: Path) -> None:
    f = tmp_path / "test_sample.py"
    f.write_text("def test_foo():\n    assert True\n")
    rule = TautologyRule()
    result = rule.check(tmp_path)
    assert result.severity == Severity.WARNING


def test_metadata_verdicts_shape(tmp_path: Path) -> None:
    f = tmp_path / "test_sample.py"
    f.write_text(
        "def test_a():\n"
        "    assert True\n"
        "\n"
        "def test_b():\n"
        "    x = 1\n"
        "    assert x == x\n"
    )
    rule = TautologyRule()
    result = rule.check(tmp_path)
    verdicts = result.metadata["verdicts"]
    assert isinstance(verdicts, list)
    assert len(verdicts) == 2
    expected_keys = {"test", "line", "pattern", "rule", "verdict", "reason"}
    for v in verdicts:
        assert isinstance(v, dict)
        assert expected_keys.issubset(v.keys())
