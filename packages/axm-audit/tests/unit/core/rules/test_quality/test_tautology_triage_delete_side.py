from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from axm_audit.core.rules.test_quality.tautology import detect_tautologies
from axm_audit.core.rules.test_quality.tautology_triage import Verdict, triage


def _build_ctx(
    source: str,
    test_file: str = "test_foo.py",
    pkg_symbols: set[str] | None = None,
    contracts: set[str] | None = None,
) -> dict[str, Any]:
    tree = ast.parse(source)
    all_funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    tests = [f for f in all_funcs if f.name.startswith("test_")]
    helpers = [f for f in all_funcs if not f.name.startswith("test_")]
    return {
        "tree": tree,
        "tests": tests,
        "helpers": helpers,
        "pkg_symbols": pkg_symbols or set(),
        "contracts": contracts or set(),
        "test_file": Path(test_file),
        "source_text": source,
    }


def _triage_first(
    source: str,
    *,
    test_file: str = "test_foo.py",
    pkg_symbols: set[str] | None = None,
    contracts: set[str] | None = None,
    target_test: str | None = None,
) -> Verdict:
    ctx = _build_ctx(
        source, test_file=test_file, pkg_symbols=pkg_symbols, contracts=contracts
    )
    findings = detect_tautologies(ctx["tree"], path=test_file)
    if target_test:
        findings = [f for f in findings if f.test == target_test]
    assert findings, "expected at least one tautology finding"
    finding = findings[0]
    func = next(f for f in ctx["tests"] if f.name == finding.test)
    return triage(
        finding,
        tree=ctx["tree"],
        func=func,
        enclosing_class=None,
        helpers=ctx["helpers"],
        pkg_symbols=ctx["pkg_symbols"],
        contracts=ctx["contracts"],
        test_file=ctx["test_file"],
        source_text=ctx["source_text"],
    )


def test_step_n2_import_smoke_deletes() -> None:
    src = "def test_smoke():\n    from mypkg import Y\n    assert Y is not None\n"
    v = _triage_first(src)
    assert v.action == "DELETE"
    assert v.rule == "step_n2_import_smoke"


def test_step_n2b_lazy_import_rescues() -> None:
    src = "def test_smoke():\n    from mypkg import Y\n    assert Y is not None\n"
    v = _triage_first(src, test_file="test_init.py")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step_n2b_lazy_import_sut"


def test_step_n2c_toplevel_import_not_none_deletes() -> None:
    src = (
        "from mypkg import Y\n"
        "\n"
        "def test_not_none():\n"
        "    assert Y is not None\n"
        "\n"
        "def test_uses_y():\n"
        "    result = Y()\n"
        "    assert result.ok\n"
    )
    v = _triage_first(src, target_test="test_not_none")
    assert v.action == "DELETE"
    assert v.rule == "step_n2c_toplevel_import_not_none"


def test_step_n2c_skipped_in_lazy_context() -> None:
    src = (
        "from mypkg import Y\n"
        "\n"
        "def test_not_none():\n"
        "    assert Y is not None\n"
        "\n"
        "def test_uses_y():\n"
        "    result = Y()\n"
        "    assert result.ok\n"
    )
    v = _triage_first(src, test_file="test_init.py", target_test="test_not_none")
    assert v.rule != "step_n2c_toplevel_import_not_none"


def test_step_n1_no_siblings_strengthens() -> None:
    src = "def test_only():\n    x = 1\n    assert isinstance(x, int)\n"
    v = _triage_first(src)
    assert v.action == "STRENGTHEN"
    assert v.rule == "step_n1_no_siblings"


def test_step0_self_compare_strengthens() -> None:
    src = (
        "def test_a():\n"
        "    x = 1\n"
        "    assert x == x\n"
        "\n"
        "def test_b():\n"
        "    assert True\n"
    )
    v = _triage_first(src, target_test="test_a")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step0_self_compare"


def test_step0c_contract_conformance_protocol() -> None:
    src = (
        "class FooProto:\n"
        "    pass\n"
        "\n"
        "def test_conforms():\n"
        "    x = object()\n"
        "    assert isinstance(x, FooProto)\n"
        "\n"
        "def test_other():\n"
        "    assert True\n"
    )
    v = _triage_first(src, contracts={"FooProto"}, target_test="test_conforms")
    assert v.action == "STRENGTHEN"


def test_step0c_contract_conformance_stdlib_mapping() -> None:
    src = (
        "from collections.abc import Mapping\n"
        "\n"
        "def test_conforms():\n"
        "    x = {}\n"
        "    assert isinstance(x, Mapping)\n"
        "\n"
        "def test_other():\n"
        "    assert True\n"
    )
    v = _triage_first(src, target_test="test_conforms")
    assert v.action == "STRENGTHEN"


def test_step0d_explicit_contract_name() -> None:
    src = (
        "def test_Foo_satisfies_AXMTool():\n"
        "    x = object()\n"
        "    assert isinstance(x, object)\n"
        "\n"
        "def test_other():\n"
        "    assert True\n"
    )
    v = _triage_first(src, target_test="test_Foo_satisfies_AXMTool")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step0d_explicit_contract_name"


def test_step1a_unique_fn_strengthens() -> None:
    src = (
        "from mypkg import foo, bar\n"
        "\n"
        "def test_foo():\n"
        "    r = foo()\n"
        "    assert isinstance(r, dict)\n"
        "\n"
        "def test_bar():\n"
        "    r = bar()\n"
        "    assert r == r\n"
    )
    v = _triage_first(src, pkg_symbols={"foo", "bar"}, target_test="test_foo")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step1a_unique_fn"


def test_step1b_different_args_before_0b() -> None:
    src = (
        "from mypkg import Foo\n"
        "\n"
        "def test_ctor_a():\n"
        "    f = Foo(name='a')\n"
        "    assert f is not None\n"
        "\n"
        "def test_ctor_b():\n"
        "    f = Foo(name='b')\n"
        "    assert f is not None\n"
    )
    v = _triage_first(src, pkg_symbols={"Foo"}, target_test="test_ctor_a")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step1b_different_args"


def test_step1b_list_kwarg_expansion() -> None:
    src = (
        "from mypkg import Foo\n"
        "\n"
        "def test_ctor_empty():\n"
        "    f = Foo(feeds=[])\n"
        "    assert f is not None\n"
        "\n"
        "def test_ctor_nonempty():\n"
        "    f = Foo(feeds=['a'])\n"
        "    assert f is not None\n"
    )
    v = _triage_first(src, pkg_symbols={"Foo"}, target_test="test_ctor_empty")
    assert v.action == "STRENGTHEN"
    assert v.rule == "step1b_different_args"


def test_step0b_n_copies_deletes() -> None:
    src = (
        "from mypkg import Foo\n"
        "\n"
        "def test_ctor_a():\n"
        "    f = Foo(name='x')\n"
        "    assert f is not None\n"
        "\n"
        "def test_ctor_b():\n"
        "    f = Foo(name='x')\n"
        "    assert f is not None\n"
    )
    v = _triage_first(src, pkg_symbols={"Foo"}, target_test="test_ctor_a")
    assert v.action == "DELETE"
    assert v.rule == "step0b_n_copies_constructor"


def test_step0b2_impure_sibling_covers_ctor() -> None:
    src = (
        "from mypkg import Foo\n"
        "\n"
        "def test_ctor_weak():\n"
        "    f = Foo(name='x')\n"
        "    assert f is not None\n"
        "\n"
        "def test_uses_foo_behavior():\n"
        "    f = Foo(name='x')\n"
        "    result = f.compute(42)\n"
        "    assert result == 84\n"
    )
    v = _triage_first(src, pkg_symbols={"Foo"}, target_test="test_ctor_weak")
    assert v.action == "DELETE"
    assert v.rule == "step0b2_impure_sibling_covers_ctor"


def test_step5_unknown_for_unclassified() -> None:
    src = (
        "def test_a():\n"
        "    x = object()\n"
        "    assert isinstance(x, object)\n"
        "\n"
        "def test_b():\n"
        "    y = 5\n"
        "    assert y > 0\n"
    )
    v = _triage_first(src, target_test="test_a")
    assert v.action == "UNKNOWN"
    assert v.rule == "step5_default_unknown"
