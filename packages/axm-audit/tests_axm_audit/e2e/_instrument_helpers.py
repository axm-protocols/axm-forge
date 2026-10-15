"""Shared subprocess guard for declared runtime e2e tests."""

import subprocess
from typing import cast

_REAL_POPEN = subprocess.Popen


def _no_uv(command: list[str], **kwargs: object) -> subprocess.Popen[str]:
    """Prohibit bootstrap while exercising a real declared child."""
    assert command[0] != "uv", "contract runtime must never invoke uv"
    return cast("subprocess.Popen[str]", _REAL_POPEN(command, **kwargs))
