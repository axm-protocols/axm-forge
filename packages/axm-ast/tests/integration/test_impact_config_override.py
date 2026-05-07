from __future__ import annotations

from pathlib import Path

import pytest

from axm_ast.core.impact import analyze_impact

pytestmark = pytest.mark.integration


def _make_pkg(tmp_path: Path, *, with_override: bool, n_callers: int) -> Path:
    pkg_root = tmp_path / "fakepkg"
    src = pkg_root / "src" / "fakepkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "core.py").write_text("def target() -> int:\n    return 1\n")

    body = "from fakepkg.core import target\n\n"
    for i in range(n_callers):
        body += f"def caller_{i}() -> int:\n    return target()\n\n"
    (src / "callers.py").write_text(body)

    pyproject = '[project]\nname = "fakepkg"\nversion = "0.1.0"\n'
    if with_override:
        pyproject += "\n[tool.axm-ast.impact]\nhigh_threshold = 2\n"
    (pkg_root / "pyproject.toml").write_text(pyproject)
    return pkg_root / "src" / "fakepkg"


def test_pyproject_override_lowers_high_threshold(tmp_path: Path) -> None:
    pkg_path = _make_pkg(tmp_path, with_override=True, n_callers=2)
    result = analyze_impact(pkg_path, "target")
    assert result["score"] == "HIGH"


def test_no_pyproject_section_uses_defaults(tmp_path: Path) -> None:
    pkg_path = _make_pkg(tmp_path, with_override=False, n_callers=2)
    result = analyze_impact(pkg_path, "target")
    assert result["score"] == "MEDIUM"
