#!/usr/bin/env python3
"""One-shot migration audit: list tests previously exempted by name-only.

Walks a package's ``tests/`` tree and flags any test that was
*implicitly* opted out of TEST_QUALITY_TAUTOLOGY by the now-removed
name-based heuristic (see AXM-1725). For each match, the test should
either receive ``pytest.mark.tautology_ok("<reason>")`` (preferred when
the assertion really is a contract check) or be strengthened to a
behavioral assertion.

Usage::

    python scripts/audit_name_based_tautology_opt_outs.py <package_path>

A test is reported when ALL of the following hold:

* it is currently flagged as a tautology by ``detect_tautologies``,
* its name matches one of the legacy ``_CONTRACT_NAME_INFIXES`` patterns
  (re-defined locally in this script — the production code no longer
  carries them),
* it is NOT a structural conformance test (i.e. the ``isinstance``
  target is not in the package's contract set).

Output is a markdown table on stdout.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from axm_audit.core.rules.test_quality._shared import collect_pkg_contract_classes
from axm_audit.core.rules.test_quality.tautology import detect_tautologies
from axm_audit.core.rules.test_quality.tautology_triage import (
    _is_contract_conformance_test,
)

_LEGACY_CONTRACT_NAME_INFIXES: tuple[str, ...] = (
    "_is_a_",
    "_is_an_",
    "_is_instance",
    "_is_cyclopts",
    "_satisfies_",
    "_satisfies",
    "_implements_",
    "_implements",
    "_conforms_to_",
    "_conforms_",
    "_is_axm_tool",
    "_is_tool_result",
    "_is_provider_port",
    "_compliance",
)


def _name_matches_legacy(name: str) -> bool:
    low = name.lower()
    return any(inf in low for inf in _LEGACY_CONTRACT_NAME_INFIXES)


def _iter_test_files(package_path: Path) -> list[Path]:
    tests_dir = package_path / "tests"
    root = tests_dir if tests_dir.exists() else package_path
    return sorted(root.rglob("test_*.py"))


def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _audit(package_path: Path) -> list[tuple[str, str]]:
    contracts: set[str] = set()
    try:
        contracts = collect_pkg_contract_classes(package_path)
    except Exception:  # noqa: BLE001
        contracts = set()

    hits: list[tuple[str, str]] = []
    for test_file in _iter_test_files(package_path):
        try:
            source = test_file.read_text()
            tree = ast.parse(source, filename=str(test_file))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        try:
            rel = str(test_file.relative_to(package_path))
        except ValueError:
            rel = str(test_file)
        findings = detect_tautologies(tree, path=rel)
        for f in findings:
            if not _name_matches_legacy(f.test):
                continue
            func = _find_func(tree, f.test)
            if func is None:
                continue
            if _is_contract_conformance_test(func, contracts):
                continue
            hits.append((rel, f.test))
    return hits


def _render(hits: list[tuple[str, str]]) -> str:
    lines = [
        "| file | test | suggested action |",
        "| -- | -- | -- |",
    ]
    for rel, test in hits:
        lines.append(
            f'| `{rel}` | `{test}` | add `pytest.mark.tautology_ok("<reason>")`'
            " or strengthen |"
        )
    if not hits:
        lines.append("| _none_ | _none_ | _no migration needed_ |")
    return "\n".join(lines) + "\n"


_EXPECTED_ARGC = 2


def main(argv: list[str]) -> int:
    if len(argv) != _EXPECTED_ARGC:
        sys.stderr.write(
            "usage: audit_name_based_tautology_opt_outs.py <package_path>\n"
        )
        return 2
    package_path = Path(argv[1]).resolve()
    if not package_path.is_dir():
        sys.stderr.write(f"not a directory: {package_path}\n")
        return 2
    hits = _audit(package_path)
    sys.stdout.write(_render(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
