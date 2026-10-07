"""Environment probe: typed errors and the plugin directory contract."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from axm_audit.core.pytest_env import (
    MIN_PYTEST_VERSION,
    PLUGIN_DIR,
    PLUGIN_MODULE,
    PytestCapabilities,
    PytestEnvironmentError,
    probe_pytest,
)


def _probe_output(payload: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, f"noise\nAXM_PROBE {payload}\n", "")


def _probe(payload: str) -> PytestCapabilities:
    with patch(
        "axm_audit.core.pytest_env.run_in_project", return_value=_probe_output(payload)
    ):
        return probe_pytest(Path("/package"))


def test_plugin_directory_exposes_the_plugin_module_only() -> None:
    importable = sorted(
        path.stem for path in PLUGIN_DIR.glob("*.py") if not path.name.startswith("_")
    )
    assert importable == [PLUGIN_MODULE]


def test_pytest_older_than_the_hooks_is_a_typed_error() -> None:
    with pytest.raises(PytestEnvironmentError) as raised:
        _probe('{"python": "/old/bin/python", "pytest": "6.2.5", "pytest_cov": true}')

    assert raised.value.interpreter == "/old/bin/python"
    assert raised.value.missing == f"pytest>={MIN_PYTEST_VERSION[0]}.0"
    assert "pytest 6.2.5" in str(raised.value)
    assert "/old/bin/python" in str(raised.value)


def test_probe_reports_coverage_capability() -> None:
    capabilities = _probe(
        '{"python": "/ok/bin/python", "pytest": "9.1.1", "pytest_cov": false}'
    )

    assert capabilities.pytest_version == "9.1.1"
    assert capabilities.coverage_available is False
    reason = capabilities.coverage_unavailable_reason
    assert reason is not None
    assert "/ok/bin/python" in reason


def test_unusable_probe_output_is_a_typed_error() -> None:
    failed = subprocess.CompletedProcess([], 127, "", "python: not found")
    with (
        patch("axm_audit.core.pytest_env.run_in_project", return_value=failed),
        pytest.raises(PytestEnvironmentError, match="python: not found"),
    ):
        probe_pytest(Path("/package"))
