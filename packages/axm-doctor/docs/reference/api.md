# Python API

All entry points below are exported from axm_doctor. Directives target defining
modules so lazy exports remain statically resolvable. Start with
[the verified narrative contracts](python.md), which qualify broader claims
in implementation docstrings.

## Detection

::: axm_doctor.detect
    options:
      members: [ToolState, AuthState, GitIdentityState, GhConfigState, ToolStatus, AuthStatus, GitIdentityStatus, GhConfigStatus, detect_tool, detect_auth, detect_git_identity, detect_gh_config]

## Provenance

::: axm_doctor.credentials
    options:
      members: [CredentialProvenance, collect_credential_provenance]

## Installation

::: axm_doctor.install
    options:
      members: [InstallPlan, InstallResult, install_command, run_install]

## Provisioning

::: axm_doctor.orchestrate
    options:
      members: [MissingSecret, ProvisionResult, missing_secrets, provision_missing]

## Tools

::: axm_doctor.tools
    options:
      members: [EnvDoctorTool, AuthStatusTool]
