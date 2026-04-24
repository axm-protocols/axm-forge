from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.base import get_registry
from axm_audit.core.rules.test_quality.private_imports import PrivateImportsRule
from axm_audit.models.results import Severity

__all__: list[str] = []


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def pkg_root(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_rule_registered_under_test_quality() -> None:
    import axm_audit.core.rules.test_quality  # noqa: F401

    registry = get_registry()
    assert "test_quality" in registry
    assert any(r is PrivateImportsRule for r in registry["test_quality"])


def test_check_empty_tests_dir_passes(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    result = PrivateImportsRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert result.details["score"] == 100


def test_check_no_src_passes(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = PrivateImportsRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert result.details["score"] == 100


def test_flags_private_function_import(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is False
    findings = result.details["findings"]  # type: ignore[index]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "function"
    assert findings[0]["private_symbol"] == "_private"


def test_flags_private_class_import(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "class _Base:\n    pass\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _Base\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]  # type: ignore[index]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "class"


def test_skips_dunder_imports(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "__init__.py",
        "__version__ = '1.0'\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg import __version__\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []  # type: ignore[index]


def test_skips_upper_case_constants_by_default(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "_REGISTRY = {}\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _REGISTRY\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert result.passed is True
    assert result.details["findings"] == []  # type: ignore[index]


def test_flags_upper_case_when_include_constants(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "_REGISTRY = {}\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _REGISTRY\n",
    )
    result = PrivateImportsRule(include_constants=True).check(pkg_root)
    findings = result.details["findings"]  # type: ignore[index]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "constant"


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


def test_score_decreases_linearly(pkg_root: Path) -> None:
    src_lines = [f"def _fn{i}():\n    return {i}\n" for i in range(10)]
    _write(pkg_root / "src" / "pkg" / "mod.py", "".join(src_lines))
    imports = "\n".join(f"from pkg.mod import _fn{i}" for i in range(10)) + "\n"
    _write(pkg_root / "tests" / "test_x.py", imports)
    result = PrivateImportsRule().check(pkg_root)
    assert result.details["score"] == 50  # type: ignore[index]


def test_score_floors_at_zero(pkg_root: Path) -> None:
    src_lines = [f"def _fn{i}():\n    return {i}\n" for i in range(25)]
    _write(pkg_root / "src" / "pkg" / "mod.py", "".join(src_lines))
    imports = "\n".join(f"from pkg.mod import _fn{i}" for i in range(25)) + "\n"
    _write(pkg_root / "tests" / "test_x.py", imports)
    result = PrivateImportsRule().check(pkg_root)
    assert result.details["score"] == 0  # type: ignore[index]


def test_message_links_to_docs(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def _private():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _private\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    assert "docs/test_quality.md#private-imports" in result.message


def test_unknown_kind_fallback(pkg_root: Path) -> None:
    _write(
        pkg_root / "src" / "pkg" / "mod.py",
        "def other():\n    return 1\n",
    )
    _write(
        pkg_root / "tests" / "test_x.py",
        "from pkg.mod import _ghost\n",
    )
    result = PrivateImportsRule().check(pkg_root)
    findings = result.details["findings"]  # type: ignore[index]
    assert len(findings) == 1
    assert findings[0]["symbol_kind"] == "unknown"
