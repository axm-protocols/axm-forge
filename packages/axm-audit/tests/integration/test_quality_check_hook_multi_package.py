from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.hooks.quality_check import QualityCheckHook

pytestmark = pytest.mark.integration


def _make_pkg(root: Path, name: str, files: dict[str, str]) -> None:
    pkg_src = root / "packages" / name / "src" / name.replace("-", "_")
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").write_text("")
    for fname, content in files.items():
        (pkg_src / fname).write_text(textwrap.dedent(content))
    (root / "packages" / name / "pyproject.toml").write_text(
        textwrap.dedent(
            f"""
            [project]
            name = "{name}"
            version = "0.0.0"
            requires-python = ">=3.12"
            """
        )
    )


def test_quality_check_hook_multi_package_has_violations_true(tmp_path: Path) -> None:
    _make_pkg(tmp_path, "pkg-broken", {"bad.py": "def f():\n    x = 1\n    return 0\n"})
    _make_pkg(tmp_path, "pkg-clean", {"ok.py": "def f() -> int:\n    return 0\n"})

    hook = QualityCheckHook()
    result = hook.execute(
        context={"working_dir": str(tmp_path)},
        categories=["lint", "type"],
    )
    assert result.metadata["has_violations"] is True
    assert "pkg-broken" in (result.text or "")


def test_quality_check_hook_multi_package_clean_workspace(tmp_path: Path) -> None:
    clean = '__all__ = ["f"]\n\ndef f() -> int:\n    return 0\n'
    _make_pkg(tmp_path, "pkg-a", {"ok.py": clean})
    _make_pkg(tmp_path, "pkg-b", {"ok.py": clean})

    hook = QualityCheckHook()
    result = hook.execute(
        context={"working_dir": str(tmp_path)},
        categories=["lint"],
    )
    assert result.metadata["has_violations"] is False
    assert result.metadata.get("summary") == "clean"
