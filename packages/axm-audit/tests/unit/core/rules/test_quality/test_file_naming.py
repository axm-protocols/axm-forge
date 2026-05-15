"""Unit tests for TEST_QUALITY_FILE_NAMING rule helpers."""

from __future__ import annotations

import ast
import textwrap
from collections import Counter
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality._shared import (
    canonical_filename,
    cli_invocation_tuple,
    first_party_symbol_counts,
)
from axm_audit.core.rules.test_quality.file_naming import FileNamingRule


def _parse_test_func(
    src: str, name: str = "test_x"
) -> tuple[ast.FunctionDef, ast.Module]:
    """Parse *src* and return (target test func, module)."""
    module = ast.parse(textwrap.dedent(src))
    func = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return func, module


def test_rule_id_constant() -> None:
    """AC1 — rule exposes the stable identifier."""
    rule = FileNamingRule()
    assert rule.rule_id == "TEST_QUALITY_FILE_NAMING"


def test_canonical_integration_k2_alphabetical() -> None:
    """AC2 — top-K=2 symbols emit snake-case dash-joined alphabetical name."""
    name = canonical_filename(
        symbols_or_tuples=("Rule", "Engine"),
        tier="integration",
        single_binary=None,
    )
    assert name == "test_engine-rule.py"


def test_canonical_integration_k1_collapses() -> None:
    """AC2 — K=1 collapses to test_{sym}.py."""
    name = canonical_filename(
        symbols_or_tuples=("Rule",),
        tier="integration",
        single_binary=None,
    )
    assert name == "test_rule.py"


def test_canonical_integration_pascalcase_to_snake() -> None:
    """AC2 — PascalCase symbols are converted to snake_case."""
    name = canonical_filename(
        symbols_or_tuples=("DependencyHygieneRule",),
        tier="integration",
        single_binary=None,
    )
    assert name == "test_dependency_hygiene_rule.py"


def test_canonical_e2e_multi_binary() -> None:
    """AC3 — multi-binary keeps the (bin, sub) prefix; tokens are snake-cased."""
    name = canonical_filename(
        symbols_or_tuples=[("pkg-cli", "do"), ("pkg-tool", "run")],
        tier="e2e",
        single_binary=None,
    )
    assert name == "test_pkg_cli-do-pkg_tool-run.py"


def test_canonical_e2e_single_binary_strip() -> None:
    """AC3 — single-binary packages strip the redundant prefix."""
    name = canonical_filename(
        symbols_or_tuples=[("axm-audit", "audit")],
        tier="e2e",
        single_binary="axm-audit",
    )
    assert name == "test_audit.py"


def test_canonical_e2e_single_binary_no_sub() -> None:
    """AC3 — single-binary with no sub-command surfaces the bare binary."""
    name = canonical_filename(
        symbols_or_tuples=[("axm-audit", "")],
        tier="e2e",
        single_binary="axm-audit",
    )
    assert name == "test_axm_audit.py"


def test_first_party_symbol_counts_basic() -> None:
    """AC2 — count direct usages of first-party symbols inside a test."""
    src = """
    from mypkg.engine import Rule, fn

    def test_x():
        Rule()
        Rule()
        fn()
    """
    func, module = _parse_test_func(src)
    counts = first_party_symbol_counts(
        test_func=func, mod_ast=module, pkg_prefixes={"mypkg"}
    )
    assert counts == Counter({"Rule": 2, "fn": 1})


def test_cli_invocation_tuple_subprocess() -> None:
    """AC3 — subprocess.run([bin, sub, ...]) yields a (bin, sub) tuple."""
    src = """
    import subprocess

    def test_x():
        subprocess.run(["pkg-cli", "do"])
    """
    func, module = _parse_test_func(src)
    counts = cli_invocation_tuple(
        test_func=func, mod_ast=module, project_scripts={"pkg-cli"}
    )
    assert counts == Counter({("pkg-cli", "do"): 1})


def test_cli_invocation_tuple_skips_plumbing() -> None:
    """AC3 — invocations of non-project scripts are ignored."""
    src = """
    import subprocess

    def test_x():
        subprocess.run(["git", "init"])
    """
    func, module = _parse_test_func(src)
    counts = cli_invocation_tuple(
        test_func=func, mod_ast=module, project_scripts={"pkg-cli"}
    )
    assert counts == Counter()


def test_unit_tier_is_skipped(tmp_path: Path) -> None:
    """AC8 — unit tier files are never flagged by the file-naming rule."""
    project = tmp_path / "proj"
    (project / "src" / "mypkg").mkdir(parents=True)
    (project / "src" / "mypkg" / "__init__.py").write_text("class Rule:\n    pass\n")
    (project / "src" / "mypkg" / "engine.py").write_text("from . import Rule\n")
    (project / "tests" / "unit").mkdir(parents=True)
    (project / "tests" / "unit" / "test_totally_unrelated_name.py").write_text(
        "from mypkg import Rule\n\ndef test_x():\n    Rule()\n"
    )
    (project / "pyproject.toml").write_text(
        '[project]\nname = "mypkg"\nversion = "0"\n'
    )

    rule = FileNamingRule()
    result = rule.check(project)
    findings = result.details.get("findings", []) if result.details else []
    assert findings == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
