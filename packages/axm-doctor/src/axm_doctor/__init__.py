"""axm-doctor.

Env bootstrap + auth-status doctor (detect, propose, orchestrate).

Re-exports are resolved lazily (PEP 562 ``__getattr__``): importing the package
does NOT eager-load :mod:`axm_doctor.orchestrate` (which imports ``axm-vault``)
or :mod:`axm_doctor.tools` (which imports ``axm.tools.base``). The stdlib-only
detection surface (``detect_tool`` / ``detect_auth``) therefore stays reachable
as the bootstrap probe even on a machine where the rest of AXM is not yet
installable — the heavier symbols are imported only when first accessed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axm_doctor.detect import (
        AuthState,
        AuthStatus,
        GhConfigState,
        GhConfigStatus,
        GitIdentityState,
        GitIdentityStatus,
        ToolState,
        ToolStatus,
        detect_auth,
        detect_gh_config,
        detect_git_identity,
        detect_tool,
    )
    from axm_doctor.install import (
        InstallPlan,
        InstallResult,
        install_command,
        run_install,
    )
    from axm_doctor.orchestrate import (
        MissingSecret,
        ProvisionResult,
        missing_secrets,
        provision_missing,
    )
    from axm_doctor.tools import AuthStatusTool, EnvDoctorTool

__all__ = [
    "AuthState",
    "AuthStatus",
    "AuthStatusTool",
    "EnvDoctorTool",
    "GhConfigState",
    "GhConfigStatus",
    "GitIdentityState",
    "GitIdentityStatus",
    "InstallPlan",
    "InstallResult",
    "MissingSecret",
    "ProvisionResult",
    "ToolState",
    "ToolStatus",
    "detect_auth",
    "detect_gh_config",
    "detect_git_identity",
    "detect_tool",
    "install_command",
    "missing_secrets",
    "provision_missing",
    "run_install",
]

# Symbol -> submodule for lazy resolution. Only ``orchestrate``/``tools`` pull
# heavy AXM deps; ``detect``/``install`` are light, but routing every export
# through one map keeps the package import itself side-effect-free.
_LAZY: dict[str, str] = {
    "AuthState": "detect",
    "AuthStatus": "detect",
    "GhConfigState": "detect",
    "GhConfigStatus": "detect",
    "GitIdentityState": "detect",
    "GitIdentityStatus": "detect",
    "ToolState": "detect",
    "ToolStatus": "detect",
    "detect_auth": "detect",
    "detect_gh_config": "detect",
    "detect_git_identity": "detect",
    "detect_tool": "detect",
    "InstallPlan": "install",
    "InstallResult": "install",
    "install_command": "install",
    "run_install": "install",
    "MissingSecret": "orchestrate",
    "ProvisionResult": "orchestrate",
    "missing_secrets": "orchestrate",
    "provision_missing": "orchestrate",
    "AuthStatusTool": "tools",
    "EnvDoctorTool": "tools",
}


def __getattr__(name: str) -> object:
    """Resolve a public symbol from its submodule on first access (PEP 562)."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(f"{__name__}.{module}"), name)


def __dir__() -> list[str]:
    """Expose the lazily-resolvable names to ``dir()`` / autocompletion."""
    return sorted(__all__)
