from __future__ import annotations

from pathlib import Path

import pytest

from axm_ingot.suite import canonical_suite_name, is_suite_name, is_suite_path


@pytest.mark.parametrize(
    ("project_name", "expected"),
    [
        ("axm-audit", "tests_axm_audit"),
        ("axm_protocols", "tests_axm_protocols"),
        ("sample.pkg", "tests_sample_pkg"),
    ],
)
def test_canonical_suite_name_normalizes_project_directory(
    project_name: str,
    expected: str,
) -> None:
    assert canonical_suite_name(Path("/workspace") / project_name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("tests", True),
        ("tests_axm_ast", True),
        ("tests_sample_pkg", True),
        ("test", False),
        ("tests-", False),
        ("contest", False),
    ],
)
def test_is_suite_name_recognizes_legacy_and_namespaced_roots(
    name: str,
    expected: bool,
) -> None:
    assert is_suite_name(name) is expected


def test_is_suite_path_recognizes_namespaced_component() -> None:
    assert is_suite_path(Path("packages/axm-ast/tests_axm_ast/unit/test_impact.py"))


def test_is_suite_path_rejects_source_test_module_name() -> None:
    assert not is_suite_path(Path("src/axm_ast/testing/helpers.py"))
