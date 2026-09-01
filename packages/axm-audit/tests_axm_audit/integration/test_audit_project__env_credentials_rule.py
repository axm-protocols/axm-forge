from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from axm_audit.core import audit_project
from axm_audit.core.rules.practices import env_credentials
from axm_audit.models.results import CheckResult

pytestmark = pytest.mark.integration

_RULE_ID = "PRACTICE_ENV_CREDENTIAL_READ"


def _write_module(project: Path, relative_path: str, source: str) -> None:
    path = project / "src" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _credential_check(project: Path) -> CheckResult:
    result = audit_project(project, category="practices")
    return next(check for check in result.checks if check.rule_id == _RULE_ID)


def _violations(check: CheckResult) -> list[dict[str, object]]:
    assert check.details is not None
    violations = check.details["violations"]
    assert isinstance(violations, list)
    return cast(list[dict[str, object]], violations)


def test_bound_credential_read_is_reported_once(tmp_path: Path) -> None:
    """AC1: flag the bound credential read, not its boolean-only guard."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
API_KEY = os.environ.get("S2_API_KEY")
if not os.environ.get("S2_API_KEY"):
    API_KEY = None
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["file"] == "app/service.py"
    assert violations[0]["line"] == 2


def test_credentials_layer_module_is_exempt(tmp_path: Path) -> None:
    """AC2: exempt a credentials-layer module but flag an ordinary module."""
    source = """import os
API_KEY = os.environ.get("S2_API_KEY")
"""
    _write_module(tmp_path, "axm_vault/credentials.py", source)
    _write_module(tmp_path, "app/service.py", source)

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["file"] == "app/service.py"
    assert all(item["file"] != "axm_vault/credentials.py" for item in violations)


def test_test_module_is_exempt(tmp_path: Path) -> None:
    """AC3: exempt test-tree code but retain the source-module violation."""
    source = """import os
API_KEY = os.environ.get("S2_API_KEY")
"""
    _write_module(tmp_path, "app/service.py", source)
    _write_module(tmp_path, "tests_pkg/test_service.py", source)

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["file"] == "app/service.py"
    assert all(item["file"] != "tests_pkg/test_service.py" for item in violations)


def test_noncredential_environment_read_is_ignored(tmp_path: Path) -> None:
    """AC4: report only the credential when ordinary environment state is read."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
LOG_LEVEL = os.environ.get("AXM_LOG_LEVEL")
API_KEY = os.environ.get("S2_API_KEY")
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["line"] == 3
    assert violations[0]["env_var"] == "S2_API_KEY"


def test_remediation_names_vault_catalogue(tmp_path: Path) -> None:
    """AC5: direct remediation to the axm-vault credential catalogue."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
API_KEY = os.environ.get("S2_API_KEY")
""",
    )

    check = env_credentials.EnvCredentialsRule().check(tmp_path)

    assert check.fix_hint is not None
    assert "axm-vault credential catalogue" in check.fix_hint
    assert "axm.credentials" in check.fix_hint


def test_module_constant_credential_read_reports_resolved_name(
    tmp_path: Path,
) -> None:
    """AC1: report a module-constant read under its resolved environment name."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
STRIPE_ENV = "STRIPE_API_KEY"
token = os.environ.get(STRIPE_ENV)
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["env_var"] == "STRIPE_API_KEY"


def test_only_constant_resolving_to_credential_is_reported(
    tmp_path: Path,
) -> None:
    """AC2: ignore a constant whose resolved value is not a credential name."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
SOCKET_ENV = "AXM_SOCKET_PATH"
STRIPE_ENV = "STRIPE_API_KEY"
sock = os.environ.get(SOCKET_ENV)
token = os.environ.get(STRIPE_ENV)
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["env_var"] == "STRIPE_API_KEY"


def test_boolean_only_constant_read_is_ignored_after_resolution(
    tmp_path: Path,
) -> None:
    """AC3: report only the bound read when the same constant guards with bool."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
STRIPE_ENV = "STRIPE_API_KEY"
token = os.environ.get(STRIPE_ENV)
enabled = bool(os.environ.get(STRIPE_ENV))
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["line"] == 3


def test_runtime_composed_name_is_ignored_beside_resolved_constant(
    tmp_path: Path,
) -> None:
    """AC4: ignore a runtime-composed name beside one resolved credential."""
    _write_module(
        tmp_path,
        "app/service.py",
        """import os
prefix = "STRIPE"
STRIPE_ENV = "STRIPE_API_KEY"
dynamic = os.environ.get(prefix + "_TOKEN")
token = os.environ.get(STRIPE_ENV)
""",
    )

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["env_var"] == "STRIPE_API_KEY"


def test_credentials_layer_constant_read_remains_exempt(
    tmp_path: Path,
) -> None:
    """AC5: exempt a resolved constant read in the credentials layer."""
    source = """import os
STRIPE_ENV = "STRIPE_API_KEY"
token = os.environ.get(STRIPE_ENV)
"""
    _write_module(tmp_path, "axm_vault/credentials.py", source)
    _write_module(tmp_path, "app/service.py", source)

    violations = _violations(_credential_check(tmp_path))

    assert len(violations) == 1
    assert violations[0]["file"] == "app/service.py"
