"""Black-box import tests for the detector bootstrap boundary."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.e2e
def test_detect_import_is_lazy_about_axm_vault() -> None:
    """AC5: detector import exposes the loader without importing axm-vault."""
    script = """
import json
import sys

import axm_doctor.detect as detect_module

print(json.dumps({
    "has_loader": hasattr(detect_module, "load_auth_declarations"),
    "vault_modules": sorted(
        name for name in sys.modules
        if name == "axm_vault" or name.startswith("axm_vault.")
    ),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == {"has_loader": True, "vault_modules": []}
