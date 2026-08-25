from __future__ import annotations

import ast
from pathlib import Path

from axm_audit.core.rules.test_quality.pyramid_level import Finding, scan_test_file


def _scan(src: str, tmp_path: Path, *, level: str = "unit") -> list[Finding]:
    pkg_root = tmp_path / "pkg"
    (pkg_root / "src").mkdir(parents=True)
    tests_dir = pkg_root / "tests"
    sub = tests_dir / level
    sub.mkdir(parents=True)
    test_file = sub / "test_sample.py"
    test_file.write_text(src)
    tree = ast.parse(src)
    return scan_test_file(
        test_file=test_file,
        tree=tree,
        pkg_root=pkg_root,
        pkg_prefixes=set(),
        init_all=None,
        tests_dir=tests_dir,
    )


def test_class_helper_io_promotes_to_integration(tmp_path: Path) -> None:
    src = (
        "class TestThing:\n"
        "    def _make_cfg(self, tmp_path):\n"
        "        p = tmp_path / 'c.yaml'\n"
        "        p.write_text('x: 1')\n"
        "        return p\n"
        "    def test_uses_helper(self, tmp_path):\n"
        "        cfg = self._make_cfg(tmp_path)\n"
        "        assert cfg\n"
    )
    findings = _scan(src, tmp_path, level="unit")
    target = [f for f in findings if "test_uses_helper" in f.function]
    assert target, f"expected a finding for test_uses_helper, got {findings!r}"
    f = target[0]
    assert f.level == "integration"
    assert f.has_real_io is True
    assert any("write_text" in s for s in f.io_signals)


def test_class_helper_no_io_stays_unit(tmp_path: Path) -> None:
    src = (
        "class TestPure:\n"
        "    def _pure(self, x):\n"
        "        return x + 1\n"
        "    def test_calls_pure(self):\n"
        "        assert self._pure(1) == 2\n"
    )
    findings = _scan(src, tmp_path, level="unit")
    target = [f for f in findings if "test_calls_pure" in f.function]
    if target:
        f = target[0]
        assert f.level == "unit"
        assert f.has_real_io is False
    # otherwise: no finding emitted because folder == classified level == unit
