"""Integration tests for declaration-driven authentication detection."""

from __future__ import annotations

import importlib
import textwrap
import time
from pathlib import Path

import pytest

import axm_doctor.detect as detect_module
from axm_doctor.detect import AuthStatus, detect_auth


def _install_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    module_name: str,
    source: str,
) -> None:
    """Install a real temporary axm.credentials declaring distribution."""
    (tmp_path / f"{module_name}.py").write_text(
        textwrap.dedent(source),
        encoding="utf-8",
    )
    dist_info = tmp_path / f"{module_name}-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {module_name}\nVersion: 1.0\n",
        encoding="utf-8",
    )
    (dist_info / "entry_points.txt").write_text(
        f"[axm.credentials]\n{module_name} = {module_name}:credentials\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()


@pytest.mark.integration
def test_declared_auth_dependency_drives_logged_in_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: a discovered auth declaration supersedes detector literals."""
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="declared_success",
        source="""
            from axm_vault import AuthDependencySpec, CredentialGroup


            class ConnectedSource:
                def status(self):
                    return "connected"


            def credentials():
                return [
                    CredentialGroup(
                        id="declared-success",
                        package="declared-success",
                        title="Declared success",
                        specs=(),
                        auth_dependencies=(
                            AuthDependencySpec(
                                name="declared-success",
                                source=ConnectedSource(),
                            ),
                        ),
                    ),
                ]
        """,
    )

    declarations = detect_module.load_auth_declarations()
    status = detect_auth("declared-success")

    assert "declared-success" in declarations
    assert status.state == "logged_in"
    assert status.login_cmd is None


@pytest.mark.integration
def test_declared_inconclusive_probe_reports_consulted_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: an inconclusive installed declaration is still reported as consulted."""
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="declared_inconclusive",
        source="""
            from axm_vault import AuthDependencySpec, CredentialGroup


            class InconclusiveSource:
                def status(self):
                    return "inconclusive"


            def credentials():
                return [
                    CredentialGroup(
                        id="declared-inconclusive",
                        package="declared-inconclusive",
                        title="Declared inconclusive",
                        specs=(),
                        auth_dependencies=(
                            AuthDependencySpec(
                                name="declared-inconclusive",
                                source=InconclusiveSource(),
                            ),
                        ),
                    ),
                ]
        """,
    )

    declarations = detect_module.load_auth_declarations()
    status = detect_auth("declared-inconclusive")

    assert "declared-inconclusive" in declarations
    assert status.state == "logged_out"
    assert status.declaration_consulted is True


@pytest.mark.integration
def test_raising_declaration_is_indeterminate_for_that_tool_alone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2: a raising probe is contained without poisoning another entry."""
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="declared_raising",
        source="""
            from axm_vault import AuthDependencySpec, CredentialGroup


            class RaisingSource:
                def status(self):
                    raise RuntimeError("probe failed")


            class ConnectedSource:
                def status(self):
                    return "connected"


            def credentials():
                return [
                    CredentialGroup(
                        id="declared-raising",
                        package="declared-raising",
                        title="Declared raising",
                        specs=(),
                        auth_dependencies=(
                            AuthDependencySpec(
                                name="declared-raising",
                                source=RaisingSource(),
                            ),
                            AuthDependencySpec(
                                name="declared-healthy",
                                source=ConnectedSource(),
                            ),
                        ),
                    ),
                ]
        """,
    )

    failed = detect_auth("declared-raising")
    healthy = detect_auth("declared-healthy")

    assert isinstance(failed, AuthStatus)
    assert failed.state == "logged_out"
    assert healthy.state == "logged_in"


@pytest.mark.integration
def test_raising_provider_does_not_hide_another_consulted_declaration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: one raising provider cannot hide another consulted declaration."""
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="provider_raising",
        source="""
            def credentials():
                raise RuntimeError("provider failed")
        """,
    )
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="provider_healthy",
        source="""
            from axm_vault import AuthDependencySpec, CredentialGroup


            class ConnectedSource:
                def status(self):
                    return "connected"


            def credentials():
                return [
                    CredentialGroup(
                        id="provider-healthy",
                        package="provider-healthy",
                        title="Provider healthy",
                        specs=(),
                        auth_dependencies=(
                            AuthDependencySpec(
                                name="provider-healthy-tool",
                                source=ConnectedSource(),
                            ),
                        ),
                    ),
                ]
        """,
    )

    declarations = detect_module.load_auth_declarations()
    status = detect_auth("provider-healthy-tool")

    assert "provider-healthy-tool" in declarations
    assert status.state == "logged_in"
    assert status.declaration_consulted is True


@pytest.mark.integration
def test_declaration_guard_delay_bounds_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: the declaration's own guard delay bounds a stalled probe."""
    _install_provider(
        tmp_path,
        monkeypatch,
        module_name="declared_slow",
        source="""
            import time

            from axm_vault import AuthDependencySpec, CredentialGroup


            class SlowSource:
                def status(self):
                    time.sleep(1.0)
                    return "connected"


            class GuardedDependency(AuthDependencySpec):
                guard_delay_s: float = 0.02


            def credentials():
                return [
                    CredentialGroup(
                        id="declared-slow",
                        package="declared-slow",
                        title="Declared slow",
                        specs=(),
                        auth_dependencies=(
                            GuardedDependency(
                                name="declared-slow",
                                source=SlowSource(),
                            ),
                        ),
                    ),
                ]
        """,
    )

    started = time.monotonic()
    status = detect_auth("declared-slow")
    elapsed = time.monotonic() - started

    assert isinstance(status, AuthStatus)
    assert status.state == "logged_out"
    assert elapsed < 0.5
