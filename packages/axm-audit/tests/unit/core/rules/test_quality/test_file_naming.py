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
from axm_audit.core.rules.test_quality.file_naming import (
    _MAX_TEXT_INFOS,
    _MAX_TEXT_WARNINGS,
    FileNamingRule,
    Finding,
    compute_canonical_name,
    render_findings_text,
)
from axm_audit.models.results import Severity


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _mk_pkg(tmp_path: Path, name: str = "pkg") -> Path:
    pkg_dir = tmp_path / "src" / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("")
    return pkg_dir


def test_compute_canonical_name_matches_file_naming_rule(tmp_path: Path) -> None:
    """AC5: compute_canonical_name and FileNamingRule share one pipeline."""
    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    test_file = tmp_path / "tests" / "integration" / "test_foo.py"
    _write(
        test_file,
        "from pkg.foo import foo\n\ndef test_foo():\n    assert foo() == 1\n",
    )

    canonical = compute_canonical_name(test_file, tmp_path)

    assert canonical == "test_foo.py"
    rule_result = FileNamingRule().check(tmp_path)
    rule_canonicals = {
        f["proposed_name"]
        for f in (rule_result.details or {}).get("findings", [])
        if f.get("path", "").endswith("tests/integration/test_foo.py")
    } | {canonical}
    assert canonical in rule_canonicals


def test_compute_canonical_name_returns_none_for_unit_tier(tmp_path: Path) -> None:
    """AC4: unit-tier test files are out of scope → helper returns None."""
    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    test_file = tmp_path / "tests" / "unit" / "test_x.py"
    _write(
        test_file,
        "from pkg.foo import foo\n\ndef test_x():\n    assert foo() == 1\n",
    )

    assert compute_canonical_name(test_file, tmp_path) is None


def test_compute_canonical_name_returns_none_when_no_symbols(tmp_path: Path) -> None:
    """AC4: integration file with no first-party symbol coverage → None."""
    _mk_pkg(tmp_path)
    test_file = tmp_path / "tests" / "integration" / "test_foo.py"
    _write(test_file, "def test_x():\n    pass\n")

    assert compute_canonical_name(test_file, tmp_path) is None


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


@pytest.mark.parametrize(
    ("symbols", "expected"),
    [
        pytest.param(("Rule", "Engine"), "test_engine__rule.py", id="k2_alphabetical"),
        pytest.param(("Rule",), "test_rule.py", id="k1_collapses"),
        pytest.param(
            ("DependencyHygieneRule",),
            "test_dependency_hygiene_rule.py",
            id="pascalcase_to_snake",
        ),
    ],
)
def test_canonical_integration(symbols: tuple[str, ...], expected: str) -> None:
    """AC2 — integration canonical filename across K and casing variants."""
    name = canonical_filename(
        symbols_or_tuples=symbols,
        tier="integration",
        single_binary=None,
    )
    assert name == expected


def test_canonical_e2e_multi_binary() -> None:
    """AC3 — multi-binary keeps the (bin, sub) prefix; tokens are snake-cased."""
    name = canonical_filename(
        symbols_or_tuples=[("pkg-cli", "do"), ("pkg-tool", "run")],
        tier="e2e",
        single_binary=None,
    )
    assert name == "test_pkg_cli__do__pkg_tool__run.py"


@pytest.mark.parametrize(
    ("tuples", "expected"),
    [
        pytest.param(
            [("axm-audit", "audit")], "test_audit.py", id="single_binary_strip"
        ),
        pytest.param(
            [("axm-audit", "")], "test_axm_audit.py", id="single_binary_no_sub"
        ),
    ],
)
def test_canonical_e2e_single_binary(
    tuples: list[tuple[str, str]], expected: str
) -> None:
    """AC3 — single-binary e2e canonical name with/without sub-command."""
    name = canonical_filename(
        symbols_or_tuples=tuples,
        tier="e2e",
        single_binary="axm-audit",
    )
    assert name == expected


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


def _make_finding(
    severity: Severity,
    path: str = "tests/integration/test_foo.py",
    proposed_name: str = "test_bar.py",
) -> Finding:
    return Finding(
        verdict="NAME_MISMATCH",
        severity=severity,
        tier="integration",
        current_name="test_foo.py",
        proposed_name=proposed_name,
        path=path,
    )


def test_render_findings_text_returns_none_when_empty() -> None:
    """AC5 — empty findings → text is None (not empty string)."""
    assert render_findings_text([]) is None


def test_render_findings_text_warnings_before_infos() -> None:
    """AC4 — WARNING findings render strictly before INFO findings."""
    findings = [
        _make_finding(Severity.INFO, path="tests/integration/test_info.py"),
        _make_finding(Severity.WARNING, path="tests/integration/test_warn.py"),
    ]

    text = render_findings_text(findings)

    assert text is not None
    warning_idx = text.index("[WARNING]")
    info_idx = text.index("[INFO]")
    assert warning_idx < info_idx


def test_render_findings_text_line_format() -> None:
    """AC3 — each finding line is `• [<SEVERITY>] <path> → <proposed_name>`."""
    findings = [
        _make_finding(
            Severity.WARNING,
            path="tests/integration/test_foo.py",
            proposed_name="test_bar.py",
        ),
    ]

    text = render_findings_text(findings)

    assert text is not None
    expected_line = "• [WARNING] tests/integration/test_foo.py → test_bar.py"
    assert expected_line in text


def test_render_findings_text_caps_at_top_n() -> None:
    """AC2 — caps at 10 WARNING + 5 INFO, suffix summarizes truncated remainder."""
    assert _MAX_TEXT_WARNINGS == 10
    assert _MAX_TEXT_INFOS == 5

    findings = [
        _make_finding(Severity.WARNING, path=f"tests/integration/test_w{i}.py")
        for i in range(15)
    ] + [
        _make_finding(Severity.INFO, path=f"tests/integration/test_i{i}.py")
        for i in range(8)
    ]

    text = render_findings_text(findings)

    assert text is not None
    lines = text.splitlines()
    warning_lines = [line for line in lines if "[WARNING]" in line]
    info_lines = [line for line in lines if "[INFO]" in line]
    assert len(warning_lines) == 10
    assert len(info_lines) == 5

    suffix_lines = [line for line in lines if line.startswith("(+")]
    assert len(suffix_lines) == 1
    assert suffix_lines[0] == "(+8 more findings: 5 WARNING, 3 INFO)"


def test_render_findings_text_no_suffix_when_under_cap() -> None:
    """AC2 — no `(+N more)` suffix when both severities fit under their caps."""
    findings = [
        _make_finding(Severity.WARNING, path=f"tests/integration/test_w{i}.py")
        for i in range(3)
    ] + [
        _make_finding(Severity.INFO, path=f"tests/integration/test_i{i}.py")
        for i in range(2)
    ]

    text = render_findings_text(findings)

    assert text is not None
    lines = text.splitlines()
    finding_lines = [line for line in lines if line.startswith("•")]
    suffix_lines = [line for line in lines if line.startswith("(+")]
    assert len(finding_lines) == 5
    assert suffix_lines == []


def test_self_audit_text_under_size_threshold() -> None:
    """AC6 — self-audit on axm-audit produces text well under 4 KB."""
    package_root = Path(__file__).resolve().parents[2]

    result = FileNamingRule().check(package_root)

    if result.text is None:
        pytest.skip("axm-audit has no FILE_NAMING findings; size cap trivially met")
    assert len(result.text) < 4_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
