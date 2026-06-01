"""Unit tests for axm_audit.core.fix.findings."""

from __future__ import annotations

import ast
import textwrap
from types import SimpleNamespace

import pytest

from axm_audit.core.fix.findings import (
    class_needs_flatten,
    func_canonical,
    normalize_findings,
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


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        pytest.param(
            SimpleNamespace(details={"findings": [{"path": "a.py"}]}),
            [{"path": "a.py"}],
            id="dict-findings",
        ),
        pytest.param(
            SimpleNamespace(
                details={
                    "findings": [
                        SimpleNamespace(
                            model_dump=lambda: {"path": "m.py", "rule": "R"}
                        )
                    ]
                }
            ),
            [{"path": "m.py", "rule": "R"}],
            id="model-dump-objects",
        ),
        pytest.param(
            SimpleNamespace(details={"findings": [SimpleNamespace(path="v.py")]}),
            [{"path": "v.py"}],
            id="plain-objects-via-vars",
        ),
        pytest.param(
            SimpleNamespace(
                details={
                    "findings": [
                        {"path": "d.py"},
                        SimpleNamespace(model_dump=lambda: {"path": "o.py"}),
                    ]
                }
            ),
            [{"path": "d.py"}, {"path": "o.py"}],
            id="mixed-dict-and-object",
        ),
    ],
)
def test_findings_normalizes_entries(
    check: SimpleNamespace, expected: list[dict[str, str]]
) -> None:
    """_findings normalizes dict, model_dump and vars-based entries in order."""
    assert normalize_findings(check) == expected


def test_findings_falls_back_to_findings_attr() -> None:
    """_findings uses the .findings attribute when details has no findings key."""
    check = SimpleNamespace(details={"other": 1}, findings=[{"path": "b.py"}])
    assert normalize_findings(check) == [{"path": "b.py"}]


def test_findings_falls_back_when_details_not_dict() -> None:
    """_findings ignores a non-dict details and reads the .findings attribute."""
    check = SimpleNamespace(details=None, findings=[{"path": "c.py"}])
    assert normalize_findings(check) == [{"path": "c.py"}]


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
    assert normalize_findings(check) == []


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
    name = func_canonical(
        func,
        mod,
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert name == "test_resolver.py"


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        pytest.param(
            """
        from pkg.mod import Resolver, Cache

        def test_it():
            Resolver()
            Cache()
    """,
            "test_cache__resolver.py",
            id="two-symbols-sorted-joined",
        ),
        pytest.param(
            """
        def test_it():
            x = 1
            assert x == 1
    """,
            "test_UNKNOWN.py",
            id="unknown-without-first-party",
        ),
    ],
)
def test_func_canonical_integration(src: str, expected: str) -> None:
    """func_canonical names integration tests from their first-party symbols."""
    name = func_canonical(
        _func(src),
        _module(src),
        tier="integration",
        pkg_prefixes={"pkg"},
        scripts=set(),
        single_binary=None,
    )
    assert name == expected


# ── _func_canonical: e2e tier ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        pytest.param(
            """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit", "audit"])
    """,
            "test_audit.py",
            id="single-binary-strips-prefix",
        ),
        pytest.param(
            """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit"])
    """,
            "test_axm_audit.py",
            id="bare-binary-keeps-binary-token",
        ),
    ],
)
def test_func_canonical_e2e_single_binary(src: str, expected: str) -> None:
    """Single-binary e2e collapses or surfaces the binary token as needed."""
    name = func_canonical(
        _func(src),
        _module(src),
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"axm-audit"},
        single_binary="axm-audit",
    )
    assert name == expected


def test_func_canonical_e2e_multi_binary_keeps_bin_and_sub() -> None:
    """Multi-binary e2e keeps the bin__sub form when single_binary is None."""
    src = """
        import subprocess

        def test_it():
            subprocess.run(["axm-audit", "audit"])
    """
    name = func_canonical(
        _func(src),
        _module(src),
        tier="e2e",
        pkg_prefixes=set(),
        scripts={"axm-audit", "axm-other"},
        single_binary=None,
    )
    assert name == "test_axm_audit__audit.py"


# ── class_needs_flatten ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("src", "expected"),
    [
        pytest.param(
            """
        from pkg.mod import Resolver, Cache

        class TestThings:
            def test_a(self):
                Resolver()
            def test_b(self):
                Cache()
    """,
            True,
            id="divergent-methods",
        ),
        pytest.param(
            """
        from pkg.mod import Resolver

        class TestThings:
            def test_a(self):
                Resolver()
            def test_b(self):
                Resolver()
    """,
            False,
            id="shared-symbol",
        ),
        pytest.param(
            """
        from pkg.mod import Resolver

        class TestThings:
            def test_only(self):
                Resolver()
    """,
            False,
            id="single-method",
        ),
    ],
)
def test_class_needs_flatten_integration(src: str, expected: bool) -> None:
    """class_needs_flatten splits only when integration symbols diverge."""
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
        is expected
    )
