"""Split from ``test_coupling_severity.py``."""

import textwrap
from pathlib import Path

from axm_audit.core.rules.architecture import CouplingMetricRule
from axm_audit.models.results import Severity
from tests.integration._helpers import _make_src_module__from_coupling_severity


def _write_pyproject(tmp_path: Path, content: str) -> None:
    """Write a pyproject.toml into *tmp_path*."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(content),
        encoding="utf-8",
    )


def test_mixed_severities_functional(tmp_path: Path) -> None:
    """Functional: mixed severities → result severity=ERROR, passed=False."""
    _write_pyproject(
        tmp_path,
        """\
            [project]
            name = "fakepkg"

            [tool.axm-audit.coupling]
            fan_out_threshold = 10
        """,
    )
    # warning-level module (12 imports, threshold=10, multiplier=2 → 12 <= 20)
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "warn_mod", n_imports=12
    )
    # error-level module (25 imports → 25 > 20)
    _make_src_module__from_coupling_severity(
        tmp_path, "fakepkg", "err_mod", n_imports=25
    )

    rule = CouplingMetricRule()
    result = rule.check(tmp_path)
    assert result.passed is False
    assert result.severity == Severity.ERROR
