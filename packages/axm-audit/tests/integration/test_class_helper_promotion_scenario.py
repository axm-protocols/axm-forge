from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality.pyramid_level import scan_package

pytestmark = pytest.mark.integration


def test_scan_package_node_fdm_pipeline_reproducer(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    (pkg / "src" / "pkg").mkdir(parents=True)
    (pkg / "src" / "pkg" / "__init__.py").write_text("")
    tests_dir = pkg / "tests"
    integ = tests_dir / "integration"
    integ.mkdir(parents=True)
    (tests_dir / "__init__.py").write_text("")
    (integ / "__init__.py").write_text("")

    src = (
        "class TestPredictPipeline:\n"
        "    def _make_config(self, tmp_path):\n"
        "        p = tmp_path / 'config.yaml'\n"
        "        p.write_text('a: 1')\n"
        "        return p\n"
        "    def test_delegates(self, tmp_path):\n"
        "        cfg = self._make_config(tmp_path)\n"
        "        assert cfg.exists()\n"
        "    def test_no_io(self):\n"
        "        assert 1 + 1 == 2\n"
    )
    (integ / "test_predict_pipeline.py").write_text(src)

    findings = scan_package(pkg)
    by_fn = {f.function: f for f in findings}

    delegating = next(
        (f for name, f in by_fn.items() if "test_delegates" in name), None
    )
    assert delegating is not None, f"missing finding for test_delegates: {by_fn!r}"
    assert delegating.level == "integration"

    no_io = next((f for name, f in by_fn.items() if "test_no_io" in name), None)
    if no_io is not None:
        # If emitted, must classify as unit (mismatch with integration folder).
        assert no_io.level == "unit"
