"""axm-doctor.

Env bootstrap + auth-status doctor (detect, propose, orchestrate)
"""

from __future__ import annotations

from axm_doctor.detect import (
    AuthState,
    AuthStatus,
    ToolState,
    ToolStatus,
    detect_auth,
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
    "InstallPlan",
    "InstallResult",
    "MissingSecret",
    "ProvisionResult",
    "ToolState",
    "ToolStatus",
    "detect_auth",
    "detect_tool",
    "install_command",
    "missing_secrets",
    "provision_missing",
    "run_install",
]
