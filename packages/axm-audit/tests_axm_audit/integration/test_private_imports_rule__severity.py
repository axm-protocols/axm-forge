"""Split from ``test_private_import_detection.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule
from axm_audit.models.results import Severity


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_severity_is_error(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.severity == Severity.ERROR
