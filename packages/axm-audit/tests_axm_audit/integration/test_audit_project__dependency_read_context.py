"""Workspace audits retain their declared runtime across worker pools."""

from __future__ import annotations

import shutil
import sys
from contextvars import ContextVar
from pathlib import Path
from threading import Barrier

import pytest
from axm.tools.dependency_reads import DependencyEnvironment, dependency_read_context
from axm.tools.write_scope import WriteContract

from axm_audit.core.auditor import audit_project
from axm_audit.core.rules._helpers import get_ast_cache
from axm_audit.core.rules.quality_rules import TypeCheckRule
from axm_audit.core.test_runner import TestReport
from axm_audit.models.results import CheckResult


@pytest.mark.integration
@pytest.mark.parametrize("reuse_reports", [False, True])
def test_workspace_type_check_uses_declared_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reuse_reports: bool,
) -> None:
    """A clean export passes, then a real type regression fails through mypy."""
    root = tmp_path / "export"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    for name in ("alpha", "beta"):
        package = root / "packages" / name
        source = package / "src" / name
        source.mkdir(parents=True)
        (package / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            "[tool.mypy]\nstrict = true\n"
        )
        (source / "__init__.py").write_text("value: int = 1\n")
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr("axm_audit.core.auditor.os.cpu_count", lambda: 2)
    assert shutil.which("mypy") is None
    contract = WriteContract(
        execution_root=str(root),
        dependency_environment=DependencyEnvironment(
            interpreter=sys.executable,
            package_root=str(root),
            pythonpath=tuple(
                str(root / "packages" / p / "src") for p in ("alpha", "beta")
            ),
        ),
    )
    barrier = Barrier(2)
    marker: ContextVar[str | None] = ContextVar("package_marker", default=None)
    caches: list[object] = []
    original_check = TypeCheckRule.check

    def concurrent_check(rule: TypeCheckRule, package: Path) -> CheckResult:
        assert marker.get() is None
        marker.set(package.name)
        cache = get_ast_cache()
        assert cache is not None
        caches.append(cache)
        barrier.wait(timeout=10)
        assert marker.get() == package.name
        return original_check(rule, package)

    monkeypatch.setattr(TypeCheckRule, "check", concurrent_check)
    reports: dict[Path, TestReport] | None = {} if reuse_reports else None
    with dependency_read_context(contract):
        clean = audit_project(root, category="type", test_reports=reports)
        assert clean.checks
        assert all(check.passed for check in clean.checks), clean.checks
        (root / "packages/beta/src/beta/__init__.py").write_text(
            'value: int = "regression"\n'
        )
        broken = audit_project(root, category="type", test_reports=reports)
    check = next(check for check in broken.checks if check.rule_id == "QUALITY_TYPE")
    assert not check.passed
    assert check.details is not None
    assert check.details["error_count"] == 1
    assert "assignment" in str(check.details["errors"])
    assert "Rule crashed" not in check.message
    assert marker.get() is None
    assert len(caches) == 4
    assert len({id(cache) for cache in caches}) == 4
