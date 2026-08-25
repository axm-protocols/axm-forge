"""Split from ``test_no_package_symbol_rule_on_synthetic_projects.py``."""

import textwrap
from pathlib import Path

from axm_audit.core.rules.base import Severity
from axm_audit.core.rules.test_quality.no_package_symbol import NoPackageSymbolRule


def _write_pkg(tmp_path: Path, *, script_name: str = "pkg-cli") -> Path:
    """Lay out a minimal package with src/pkg + tests/ + [project.scripts]."""
    pkg_root = tmp_path / "pkg-proj"
    (pkg_root / "src" / "pkg" / "core").mkdir(parents=True)
    (pkg_root / "src" / "pkg" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "__init__.py").write_text("")
    (pkg_root / "src" / "pkg" / "core" / "mod.py").write_text(
        "def fn() -> int:\n    return 1\n\nclass Rule:\n    pass\n"
    )
    (pkg_root / "tests").mkdir()
    (pkg_root / "tests" / "unit").mkdir()
    (pkg_root / "tests" / "integration").mkdir()
    (pkg_root / "tests" / "e2e").mkdir()
    (pkg_root / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "pkg"
            version = "0.0.0"

            [project.scripts]
            {script_name} = "pkg.cli:main"
            """
        ).strip()
    )
    return pkg_root


def test_severity_and_score(tmp_path: Path) -> None:
    """AC6: one finding -> severity=WARNING, score=98."""
    pkg_root = _write_pkg(tmp_path)
    (pkg_root / "tests" / "integration" / "test_x.py").write_text(
        "def test_x():\n    assert 1 + 1 == 2\n"
    )
    rule = NoPackageSymbolRule()
    result = rule.check(pkg_root)
    assert result.severity == Severity.WARNING
    assert result.score == 98
