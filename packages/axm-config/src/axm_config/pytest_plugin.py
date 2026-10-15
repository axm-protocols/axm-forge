"""pytest11 plugin: every pytest session runs inside a fresh AXM sandbox.

Registered under the ``pytest11`` entry point, so any pytest session in an
environment where axm-config is installed resolves the six AXM state paths
under an ephemeral ``mkdtemp`` root instead of the real ``~/axm`` state.
The sandbox lives in ``AXM_SANDBOX_*`` environment keys, so subprocesses
spawned by tests inherit it. Bypass with ``-p no:axm_config``.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from axm_config.sandbox import SessionSandbox

__all__ = ["pytest_configure", "pytest_unconfigure"]

# axm_config modules are imported inside the hooks, not at module level:
# this plugin loads before pytest-cov starts measuring.
_SANDBOX_KEY: pytest.StashKey[tuple[SessionSandbox, Path]] = pytest.StashKey()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Activate a sandbox on a fresh temporary root for this session."""
    from axm_config.sandbox import SandboxEscapeError, activate_sandbox

    root = Path(tempfile.mkdtemp(prefix="axm-"))
    try:
        sandbox = activate_sandbox(root)
    except SandboxEscapeError as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise pytest.UsageError(str(exc)) from exc
    config.stash[_SANDBOX_KEY] = (sandbox, root)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the pre-session environment and remove the sandbox root."""
    entry = config.stash.get(_SANDBOX_KEY, None)
    if entry is None:
        return
    from axm_config.sandbox import deactivate_sandbox

    del config.stash[_SANDBOX_KEY]

    sandbox, root = entry
    deactivate_sandbox(sandbox)
    shutil.rmtree(root, ignore_errors=True)
