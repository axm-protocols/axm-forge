"""Unit tests for axm_audit.core.rules.architecture.uv_workspace_locality.

Pure, in-memory tests of the scanner + exemption predicate. The full
filesystem-walking ``check()`` is exercised in tests/integration.
"""

from __future__ import annotations

from axm_audit.core.rules.architecture.uv_workspace_locality import (
    UvWorkspaceLocalityRule,
    is_exempt_path,
    scan_source,
)

_FAULTY_GET_CHAIN = (
    "import tomllib\n"
    "\n"
    "def resolve(data):\n"
    '    return data.get("tool", {}).get("uv", {}).get("workspace", {})\n'
)

_FAULTY_SECTION_LITERAL = (
    'HEADER = "[tool.uv.workspace]"\n\ndef emit():\n    return HEADER\n'
)

_FAULTY_DOTTED_LITERAL = 'KEY = "tool.uv.workspace"\n'

_CLEAN_SOURCE = (
    "import tomllib\n"
    "\n"
    "def resolve(data):\n"
    '    return data.get("tool", {}).get("hatch", {})\n'
)


def test_flags_workspace_parsing_outside_ingot() -> None:
    """AC1,AC2: the .get('uv').get('workspace') chain is flagged with a line."""
    sites = scan_source(_FAULTY_GET_CHAIN)

    assert sites, "a workspace .get chain must be flagged"
    linenos = {lineno for lineno, _symbol in sites}
    assert 4 in linenos, f"expected the offending line (4) in {linenos}"


def test_flags_section_literal() -> None:
    """AC1: the textual ``[tool.uv.workspace]`` section literal is flagged."""
    sites = scan_source(_FAULTY_SECTION_LITERAL)

    assert sites, "a [tool.uv.workspace] literal must be flagged"


def test_flags_dotted_literal() -> None:
    """AC1: the textual ``tool.uv.workspace`` dotted literal is flagged."""
    sites = scan_source(_FAULTY_DOTTED_LITERAL)

    assert sites, "a tool.uv.workspace literal must be flagged"


def test_clean_module_no_finding() -> None:
    """AC1: a module that does not touch tool.uv.workspace is clean."""
    sites = scan_source(_CLEAN_SOURCE)

    assert sites == []


def test_docstring_mention_not_flagged() -> None:
    """AC4: a docstring mentioning the key documents, it does not parse."""
    source = (
        "def resolve(p):\n"
        '    """Resolve members from [tool.uv.workspace] via ingot."""\n'
        "    return None\n"
    )

    assert scan_source(source) == []


def test_ingot_is_exempt() -> None:
    """AC3: paths under axm_ingot/ are exempt (the canonical seat)."""
    assert is_exempt_path("axm_ingot/uv.py") is True
    assert is_exempt_path("axm_ingot/sub/resolver.py") is True


def test_tests_paths_are_exempt() -> None:
    """AC3: test files and fixtures (string literals in tests) are exempt."""
    assert is_exempt_path("tests/unit/test_thing.py") is True
    assert is_exempt_path("conftest.py") is True
    assert is_exempt_path("pkg/tests/test_x.py") is True


def test_business_module_not_exempt() -> None:
    """AC1,AC3: an ordinary business module is not exempt."""
    assert is_exempt_path("axm_audit/core/auditor.py") is False


def test_rule_own_module_is_exempt() -> None:
    """AC4: the rule's own module holds the marker constants by definition."""
    assert (
        is_exempt_path("axm_audit/core/rules/architecture/uv_workspace_locality.py")
        is True
    )


def test_rule_id_and_category() -> None:
    """AC1: the rule advertises a stable id under the architecture category."""
    rule = UvWorkspaceLocalityRule()

    assert rule.rule_id == "ARCH_UV_WORKSPACE_LOCALITY"
    assert rule.category == "architecture"
