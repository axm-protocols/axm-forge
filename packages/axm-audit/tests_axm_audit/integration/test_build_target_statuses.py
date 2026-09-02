"""Integration tests for target identity across nested pytest roots."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.test_runner import _build_target_statuses


def _write_homonymous_workspace(root: Path) -> Path:
    package_root = root / "packages" / "pkg"
    other_root = root / "packages" / "other"
    for member_root in (package_root, other_root):
        tests = member_root / "tests"
        tests.mkdir(parents=True)
        (tests / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    return package_root


@pytest.mark.integration
def test_homonymous_target_from_other_package_remains_omitted(tmp_path: Path) -> None:
    """AC2: absolute identity rejects a homonymous test in another package."""
    package_root = _write_homonymous_workspace(tmp_path)
    pkg_target = "packages/pkg/tests/test_sample.py::test_ok"
    other_target = "packages/other/tests/test_sample.py::test_ok"
    report_data: dict[str, object] = {
        "root": str(package_root),
        "tests": [{"nodeid": "tests/test_sample.py::test_ok"}],
    }

    statuses = _build_target_statuses(
        tmp_path,
        [pkg_target, other_target],
        report_data,
    )

    assert statuses == [
        {"target": pkg_target, "status": "validated"},
        {"target": other_target, "status": "omitted"},
    ]


@pytest.mark.integration
def test_directory_target_matches_node_below_package_report_root(
    tmp_path: Path,
) -> None:
    """AC4: a directory target contains nodes resolved from the report root."""
    package_root = _write_homonymous_workspace(tmp_path)
    target = "packages/pkg/tests"
    report_data: dict[str, object] = {
        "root": str(package_root),
        "tests": [{"nodeid": "tests/test_sample.py::test_ok"}],
    }

    statuses = _build_target_statuses(tmp_path, [target], report_data)

    assert statuses == [{"target": target, "status": "validated"}]
