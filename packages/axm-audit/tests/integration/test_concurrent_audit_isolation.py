from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project
from axm_audit.core.rules._helpers import get_active_cache


def _make_minimal_package(base: Path, name: str) -> Path:
    """Create a minimal Python package under *base*."""
    pkg = base / name
    src = pkg / "src" / name
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(
        """from __future__ import annotations\n\n__all__: list[str] = []\n"""
    )
    (src / "core.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )
    (pkg / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'
    )
    return pkg


@pytest.mark.integration
def test_concurrent_audit_project_does_not_race(tmp_path: Path) -> None:
    """AC1, AC2: Two concurrent audit_project calls each get their own cache."""
    pkg_a = _make_minimal_package(tmp_path, "pkg_a")
    pkg_b = _make_minimal_package(tmp_path, "pkg_b")

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(audit_project, pkg_a)
        fut_b = pool.submit(audit_project, pkg_b)
        result_a = fut_a.result(timeout=60)
        result_b = fut_b.result(timeout=60)

    # Both returned valid AuditResult with checks
    assert result_a.checks is not None
    assert result_b.checks is not None

    # No check should contain a cache-was-None failure
    for check in [*result_a.checks, *result_b.checks]:
        if hasattr(check, "metadata") and check.metadata:
            assert "cache was None" not in str(check.metadata).lower()

    # After both calls, the active cache in main thread must be None
    assert get_active_cache() is None
