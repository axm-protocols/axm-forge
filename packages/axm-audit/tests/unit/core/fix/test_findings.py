"""Unit tests for axm_audit.core.fix.findings."""

from __future__ import annotations

import ast
import textwrap
from types import SimpleNamespace

import pytest

from axm_audit.core.fix.findings import (
    _findings,
    _func_canonical,
    class_needs_flatten,
)


def _func(src: str, name: str = "test_it") -> ast.FunctionDef:
    """Parse *src* and return the top-level test function named *name*."""
    tree = ast.parse(textwrap.dedent(src))
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    return node


def _module(src: str) -> ast.Module:
    """Parse *src* into a module AST."""
    return ast.parse(textwrap.dedent(src))


def _class(src: str) -> ast.ClassDef:
    """Parse *src* and return its first top-level class definition."""
    tree = ast.parse(textwrap.dedent(src))
    return next(n for n in tree.body if isinstance(n, ast.ClassDef))


# ── _findings: normalization branches ─────────────────────────────────


def test_findings_reads_details_dict_findings() -> None:
    """_findings prefers a list of dicts under check.details['findings']."""
    check = SimpleNamespace(details={"findings": [{"path": "a.py"}]})
    assert _findings(check) == [{"path": "a.py"}]


def test_findings_falls_back_to_findings_attr() -> None:
    """_findings uses the .findings attribute when details has no findings key."""
    check = SimpleNamespace(details={"other": 1}, findings=[{"path": "b.py"}])
    assert _findings(check) == [{"path": "b.py"}]


def test_findings_falls_back_when_details_not_dict() -> None:
    """_findings ignores a non-dict details and reads the .findings attribute."""
    check = SimpleNamespace(details=None, findings=[{"path": "c.py"}])
    assert _findings(check) == [{"path": "c.py"}]


@pytest.mark.parametrize(
    "check",
    [
        SimpleNamespace(details={"findings": []}),
        SimpleNamespace(details={}, findings=None),
        SimpleNamespace(details={"findings": None}, findings=[]),
    ],
)
def test_findings_returns_empty_for_no_findings(check: SimpleNamespace) -> None:
    """_findings returns [] when no usable findings are present."""
    assert _findings(check) == []


def test_findings_normalizes_model_dump_objects() -> None:
    """_findings calls model_dump() on finding objects that expose it."""
    item = SimpleNamespace(model_dump=lambda: {"path": "m.py", "rule": "R"})
    check = SimpleNamespace(details={"findings": [item]})
    assert _findings(check) == [{"path": "m.py", "rule": "R"}]


def test_findings_normalizes_plain_objects_via_vars() -> None:
    """_findings falls back to vars() for plain objects without model_dump."""

    class _Raw:
        def __init__(self) -> None:
            self.path = "v.py"

    check = SimpleNamespace(details={"findings": [_Raw()]})
    assert _findings(check) == [{"path": "v.py"}]


def test_findings_mixes_dict_and_object_entries() -> None:
    """_findings normalizes a heterogeneous list preserving order."""
    obj = SimpleNamespace(model_dump=lambda: {"path": "o.py"})
    check = SimpleNamespace(details={"findings": [{"path": "d.py"}, obj]})
    assert _findings(check) == [{"path": "d.py"}, {"path": "o.py"}]


# ── _func_canonical: integration tier ─────────────────────────────────


def test_func_canonical_integration_single_symbol() -> None:
    """A single first-party symbol yields a one-token canonical name."""
    mod = _module(
        """
        from pkg.mod import Resolver

        def test_it():
            Resolver()
        """
    )
    func = _func(
        """
        from pkg.mod import Resolver

        def test_it():
            Resolver()
        """
    )
    name = _func_canonical(
        func,
        mod,
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert name == "test_resolver.py"


def test_func_canonical_integration_two_symbols_sorted_joined() -> None:
    """Two first-party symbols are snake-cased, alphabetized and joined by __."""
    src = """
        from pkg.mod import Resolver, Cache

        def test_it():
            Resolver()
            Cache()
    """
    name = _func_canonical(
        _func(src),
        _module(src),
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert name == "test_cache__resolver.py"


def test_func_canonical_integration_unknown_without_first_party() -> None:
    """With no first-party symbols the integration canonical is test_UNKNOWN.py."""
    src = """
        def test_it():
            x = 1
            assert x == 1
    """
    name = _func_canonical(
        _func(src),
        _module(src),
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert name == "test_UNKNOWN.py"


# ── _func_canonical: e2e tier ─────────────────────────────────────────


def test_func_canonical_e2e_single_binary_strips_prefix() -> None:
    """Single-binary e2e collapses (bin, sub) to the sub-command token."""
    src = """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit", "audit"])
    """
    name = _func_canonical(
        _func(src),
        _module(src),
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"axm-audit"},
        single_binary="axm-audit",
    )
    assert name == "test_audit.py"


def test_func_canonical_e2e_bare_binary_keeps_binary_token() -> None:
    """A bare-binary invocation surfaces the snake-cased binary name."""
    src = """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit"])
    """
    name = _func_canonical(
        _func(src),
        _module(src),
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"axm-audit"},
        single_binary="axm-audit",
    )
    assert name == "test_axm_audit.py"


def test_func_canonical_e2e_multi_binary_keeps_bin_and_sub() -> None:
    """Multi-binary e2e keeps the bin__sub form when single_binary is None."""
    src = """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit", "audit"])
    """
    name = _func_canonical(
        _func(src),
        _module(src),
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"axm-audit", "axm-other"},
        single_binary=None,
    )
    assert name == "test_axm_audit__audit.py"


# ── class_needs_flatten ───────────────────────────────────────────────


def test_class_needs_flatten_true_for_divergent_methods() -> None:
    """A class whose methods target distinct symbols needs flattening."""
    src = """
        from pkg.mod import Resolver, Cache

        class TestThings:
            def test_a(self):
                Resolver()
            def test_b(self):
                Cache()
    """
    cls = _class(src)
    assert (
        class_needs_flatten(
            cls,
            _module(src),
            tier="integration",
            pkg_prefixes={"pkg"},
            scripts=set(),
            single_binary=None,
        )
        is True
    )


def test_class_needs_flatten_false_for_shared_symbol() -> None:
    """A class whose methods share one symbol resolves to a single canonical."""
    src = """
        from pkg.mod import Resolver

        class TestThings:
            def test_a(self):
                Resolver()
            def test_b(self):
                Resolver()
    """
    cls = _class(src)
    assert (
        class_needs_flatten(
            cls,
            _module(src),
            tier="integration",
            pkg_prefixes={"pkg"},
            scripts=set(),
            single_binary=None,
        )
        is False
    )


def test_class_needs_flatten_false_for_single_method() -> None:
    """A class with one test method has a single canonical and stays unsplit."""
    src = """
        from pkg.mod import Resolver

        class TestThings:
            def test_only(self):
                Resolver()
    """
    cls = _class(src)
    assert (
        class_needs_flatten(
            cls,
            _module(src),
            tier="integration",
            pkg_prefixes={"pkg"},
            scripts=set(),
            single_binary=None,
        )
        is False
    )
