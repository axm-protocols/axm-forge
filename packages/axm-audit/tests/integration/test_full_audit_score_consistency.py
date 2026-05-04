from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.auditor import audit_project

pytestmark = pytest.mark.integration


def _make_minimal_pkg(root: Path) -> Path:
    pkg = root / "sample_pkg"
    (pkg / "src" / "sample_pkg").mkdir(parents=True)
    (pkg / "tests").mkdir()
    (pkg / "src" / "sample_pkg" / "__init__.py").write_text(
        '"""sample."""\nfrom __future__ import annotations\n\n__all__: list[str] = []\n'
    )
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "sample-pkg"\nversion = "0.0.1"\n'
        'requires-python = ">=3.12"\n\n'
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n'
    )
    (pkg / "README.md").write_text("# sample\n")
    return pkg


def test_full_audit_score_consistency(tmp_path: Path) -> None:
    pkg = _make_minimal_pkg(tmp_path)
    report1 = audit_project(pkg)
    report2 = audit_project(pkg)
    assert report1.quality_score == report2.quality_score
