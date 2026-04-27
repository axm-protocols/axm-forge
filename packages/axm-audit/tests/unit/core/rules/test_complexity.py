from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from axm_audit.core.rules.complexity import ComplexityRule


@pytest.fixture
def rule() -> ComplexityRule:
    return ComplexityRule()


def _write(tmp_path: Path, body: str) -> Path:
    src = tmp_path / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    module = src / "m.py"
    module.write_text(body, encoding="utf-8")
    return tmp_path


def test_complexipy_dep_declared() -> None:
    pkg_root = Path(__file__).resolve().parents[4]
    pyproject = pkg_root / "pyproject.toml"
    cfg = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = cfg["project"]["dependencies"]
    assert any(d.startswith("complexipy") for d in deps), deps


def test_low_cc_high_cognitive_flagged(tmp_path: Path, rule: ComplexityRule) -> None:
    body = (
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
    project = _write(tmp_path, body)
    result = rule.check(project)
    assert result.details["high_complexity_count"] == 1
    top = result.details["top_offenders"][0]
    assert top["reason"] == "cog"


def test_high_cc_low_cognitive_flagged_as_cc(
    tmp_path: Path, rule: ComplexityRule
) -> None:
    cases = "\n".join(f"        case {i}: return {i}" for i in range(1, 13))
    body = f"def big_match(x):\n    match x:\n{cases}\n        case _: return -1\n"
    project = _write(tmp_path, body)
    result = rule.check(project)
    assert result.details["high_complexity_count"] == 1
    top = result.details["top_offenders"][0]
    assert top["reason"] == "cc"


def test_both_thresholds_single_violation(tmp_path: Path, rule: ComplexityRule) -> None:
    body = (
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
    project = _write(tmp_path, body)
    result = rule.check(project)
    assert result.details["high_complexity_count"] == 1
    top = result.details["top_offenders"][0]
    assert top["reason"] == "cc+cog"


def test_offenders_sorted_by_max_metric(tmp_path: Path, rule: ComplexityRule) -> None:
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
    project = _write(tmp_path, func_a + "\n\n" + func_b)
    result = rule.check(project)
    offenders = result.details["top_offenders"]
    assert len(offenders) == 2
    assert offenders[0]["function"] == "func_b"


def test_offender_dict_has_cognitive_key(tmp_path: Path, rule: ComplexityRule) -> None:
    cases = "\n".join(f"        case {i}: return {i}" for i in range(1, 16))
    body = f"def cc_only(x):\n    match x:\n{cases}\n        case _: return -1\n"
    project = _write(tmp_path, body)
    result = rule.check(project)
    top = result.details["top_offenders"][0]
    assert "cognitive" in top
    assert top["cognitive"] == 0
