"""Black-box coverage for tool secret-location auditing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_PACKAGE_ROOT = Path(__file__).parents[2]
_MODULES = {
    "auth_session_path.py": ('CLAUDE_SESSION_PATH = "~/.claude/.credentials.json"\n'),
    "auth_keyring_service.py": (
        "import keyring\n\n"
        'user = "probe"\n'
        'CREDENTIAL = keyring.get_password("Claude Code-credentials", user)\n'
    ),
    "auth_probe_only.py": (
        'import subprocess\n\nSTATUS = subprocess.run(["gh", "auth", "status"])\n'
    ),
    "auth_internal_paths.py": (
        "import keyring\n\n"
        'SESSION_PATH = "~/.probe_pkg/credentials.json"\n'
        'user = "probe"\n'
        'CREDENTIAL = keyring.get_password("probe_pkg-credentials", user)\n'
    ),
}


def _build_project(root: Path) -> Path:
    """Create a src-layout project containing all detector modules."""
    package_dir = root / "src" / "probe_pkg"
    auth_dir = package_dir / "auth"
    auth_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (auth_dir / "__init__.py").write_text("", encoding="utf-8")
    for module_name, body in _MODULES.items():
        (auth_dir / module_name).write_text(body, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "probe-pkg"\nversion = "0.1.0"\n'
        '\n[tool.axm-audit.mirror]\nexempt_paths = ["auth/*.py"]\n',
        encoding="utf-8",
    )
    return root


def test_audit_reports_only_third_party_secret_locations(tmp_path: Path) -> None:
    """AC4: a fresh practices audit prints exactly the offending modules."""
    project = _build_project(tmp_path)

    completed = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "axm",
            "audit",
            str(project),
            "--category",
            "practices",
        ],
        cwd=_PACKAGE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    output = completed.stdout
    assert "PRACTICE_TOOL_SECRET_LOCATION" in output
    assert "auth_session_path.py" in output
    assert "auth_keyring_service.py" in output
    assert "auth_probe_only.py" not in output
    assert "auth_internal_paths.py" not in output
