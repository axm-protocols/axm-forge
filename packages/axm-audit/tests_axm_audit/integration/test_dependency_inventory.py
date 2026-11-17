"""Exercise the lock-scoped vulnerability inventory."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from axm_audit.core.rules.dependencies import DependencyAuditRule
from axm_audit.core.rules.dependency_inventory import export_inventory

pytestmark = pytest.mark.integration


@pytest.fixture
def locked_project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.0"\n'
    )
    (tmp_path / "uv.lock").write_text(
        """version = 1
revision = 3
requires-python = ">=3.12"

[[package]]
name = "example"
version = "1.0"
source = { virtual = "." }
dependencies = [{ name = "local" }, { name = "direct" }]

[[package]]
name = "local"
version = "1.0"
source = { editable = "local" }
dependencies = [{ name = "setuptools" }]

[[package]]
name = "direct"
version = "2.0"
source = { registry = "https://pypi.org/simple" }
dependencies = [{ name = "transitive" }]

[[package]]
name = "transitive"
version = "3.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "setuptools"
version = "4.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "unrelated"
version = "8.0"
source = { registry = "https://pypi.org/simple" }
"""
    )
    return tmp_path


def test_export_follows_locked_runtime_only(locked_project: Path) -> None:
    inventory, evidence = export_inventory(locked_project)
    assert set(inventory.splitlines()) == {
        "direct==2.0",
        "setuptools==4.0",
        "transitive==3.0",
    }
    assert (
        evidence["lock_sha256"]
        == hashlib.sha256((locked_project / "uv.lock").read_bytes()).hexdigest()
    )
    assert (
        evidence["inventory_sha256"] == hashlib.sha256(inventory.encode()).hexdigest()
    )
    assert evidence["freshness"] == "not verified"


def test_empty_runtime_inventory_needs_no_scanner(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "empty"\nversion = "1.0"\n'
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\nrevision = 3\nrequires-python = ">=3.12"\n'
        '[[package]]\nname = "empty"\nversion = "1.0"\nsource = { virtual = "." }\n'
    )
    result = DependencyAuditRule().check(tmp_path)
    assert result.passed
    assert result.score == 100
    assert result.metadata["inventory"]["mode"] == "locked-runtime"


def test_missing_or_ambiguous_project_is_unavailable(locked_project: Path) -> None:
    lock = locked_project / "uv.lock"
    lock.write_text(
        lock.read_text()
        + '\n[[package]]\nname="example"\nversion="1.0"\nsource={virtual="."}\n'
    )
    result = DependencyAuditRule().check(locked_project)
    assert not result.passed
    assert result.score is None
    assert result.details["status"] == "unavailable"


def test_markers_choose_one_locked_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import axm_audit.core.rules.dependencies as module

    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "example==1 ; sys_platform == 'never'\nexample==2 ; sys_platform != 'never'\n"
    )

    def runner(
        cmd: list[str], project: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 -- invokes the test interpreter
            [sys.executable, *cmd[1:]], capture_output=True, text=True, check=False
        )

    monkeypatch.setattr(module, "run_in_project", runner)
    assert module._active_inventory(tmp_path, requirements) == {"example": "2"}


def test_scanner_scope_and_incomplete_result(
    locked_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import axm_audit.core.rules.dependencies as module

    def runner(
        cmd: list[str], project: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["python", "-c"]:
            return subprocess.run(  # noqa: S603 -- invokes the test interpreter
                [sys.executable, *cmd[1:]], capture_output=True, text=True, check=False
            )
        assert cmd[:3] == ["python", "-m", "pip_audit"]
        assert "--no-deps" in cmd and "--disable-pip" in cmd
        data = {
            "dependencies": [
                {
                    "name": name,
                    "version": version,
                    "vulns": (
                        [{"id": "CVE-1", "fix_versions": []}]
                        if name == "setuptools"
                        else []
                    ),
                }
                for name, version in (
                    ("direct", "2.0"),
                    ("setuptools", "4.0"),
                    ("transitive", "3.0"),
                )
            ]
        }
        return subprocess.CompletedProcess(cmd, 1, json.dumps(data), "")

    monkeypatch.setattr(module, "run_in_project", runner)
    result = DependencyAuditRule().check(locked_project)
    assert result.details["vuln_count"] == 1
    assert result.details["top_vulns"][0]["name"] == "setuptools"
    assert result.metadata["inventory"]["mode"] == "locked-runtime"

    def incomplete(
        cmd: list[str], project: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["python", "-c"]:
            return runner(cmd, project, **kwargs)
        return subprocess.CompletedProcess(cmd, 0, '{"dependencies": []}', "")

    monkeypatch.setattr(module, "run_in_project", incomplete)
    result = DependencyAuditRule().check(locked_project)
    assert not result.passed
    assert result.score is None

    def skipped(
        cmd: list[str], project: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["python", "-c"]:
            return runner(cmd, project, **kwargs)
        return subprocess.CompletedProcess(
            cmd, 0, '{"dependencies": [{"name":"direct","skip_reason":"unknown"}]}', ""
        )

    monkeypatch.setattr(module, "run_in_project", skipped)
    result = DependencyAuditRule().check(locked_project)
    assert not result.passed
    assert result.score is None
