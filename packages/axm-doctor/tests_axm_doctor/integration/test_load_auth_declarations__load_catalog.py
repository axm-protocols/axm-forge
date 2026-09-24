"""Integration: doctor's auth declarations agree with the vault catalog.

Each test installs real distributions (module + dist-info) on ``tmp_path`` and
lets ``importlib.metadata`` discover their ``axm.credentials`` entry points:
neither ``entry_points`` nor ``load_catalog`` is mocked.
"""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from axm_vault import load_catalog

from axm_doctor import detect as detect_module

pytestmark = pytest.mark.integration

Installer = Callable[[str, str], None]


def _clear_discovery_caches() -> None:
    cache_clear = getattr(load_catalog, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
    importlib.invalidate_caches()


def _catalog_auth_names() -> set[str]:
    return {d.name for g in load_catalog().groups() for d in g.auth_dependencies}


@pytest.fixture
def baseline_auth_names() -> set[str]:
    """Auth names declared by the environment before any fixture install."""
    _clear_discovery_caches()
    return _catalog_auth_names()


@pytest.fixture
def install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, baseline_auth_names: set[str]
) -> Iterator[Installer]:
    """Install a real distribution exposing one ``axm.credentials`` provider."""
    installed: list[str] = []

    def _install(module: str, source: str) -> None:
        (tmp_path / f"{module}.py").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )
        dist_info = tmp_path / f"{module}-0.0.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {module}\nVersion: 0.0.0\n",
            encoding="utf-8",
        )
        (dist_info / "entry_points.txt").write_text(
            f"[axm.credentials]\n{module} = {module}:provide\n", encoding="utf-8"
        )
        installed.append(module)
        monkeypatch.syspath_prepend(str(tmp_path))
        _clear_discovery_caches()

    _clear_discovery_caches()
    yield _install
    for module in installed:
        sys.modules.pop(module, None)
    _clear_discovery_caches()


_PARTIAL_INVALID = """
from axm_vault import AuthDependencySpec, CredentialGroup


class _Source:
    def status(self):
        return "connected"


def provide():
    return [
        CredentialGroup(
            id="doctortest.partialclaude",
            package="partial-claude",
            title="Partial claude",
            specs=(),
            auth_dependencies=(
                AuthDependencySpec(
                    name="claude",
                    login_command="claude login",
                    source=_Source(),
                ),
            ),
        ),
        "junk",
    ]
"""

_NON_ITERABLE = """
def provide():
    return 42
"""

_HEALTHY_CODEX = """
from axm_vault import AuthDependencySpec, CredentialGroup


class _Source:
    def status(self):
        return "connected"


def provide():
    return [
        CredentialGroup(
            id="doctortest.healthycodex",
            package="healthy-codex",
            title="Healthy codex",
            specs=(),
            auth_dependencies=(
                AuthDependencySpec(
                    name="codex",
                    login_command="codex login",
                    source=_Source(),
                ),
            ),
        ),
    ]
"""


def test_partially_invalid_contribution_contributes_no_declaration(
    install: Installer, baseline_auth_names: set[str]
) -> None:
    """AC1: a partially invalid contribution adds no declaration, as in vault."""
    install("doctor_ac1_partial_mod", _PARTIAL_INVALID)

    declarations = detect_module.load_auth_declarations()
    catalog_names = _catalog_auth_names()

    assert "claude" not in declarations
    assert set(declarations) == catalog_names
    assert catalog_names - baseline_auth_names == set()


def test_non_iterable_provider_yields_no_declarations(
    install: Installer, baseline_auth_names: set[str]
) -> None:
    """AC2: a provider returning 42 is rejected instead of raising TypeError."""
    install("doctor_ac2_non_iterable_mod", _NON_ITERABLE)

    declarations = detect_module.load_auth_declarations()

    assert set(declarations) == baseline_auth_names
    assert set(declarations) - baseline_auth_names == set()


def test_detect_auth_ignores_rejected_contribution_declaration(
    install: Installer,
) -> None:
    """AC3: a rejected contribution's 'claude' declaration is never consulted."""
    install("doctor_ac3_partial_mod", _PARTIAL_INVALID)

    status = detect_module.detect_auth("claude")

    assert isinstance(status, detect_module.AuthStatus)
    assert status.declaration_consulted is False


def test_detect_auth_survives_non_iterable_provider(install: Installer) -> None:
    """AC4: detect_auth does not raise when a provider returns a non-iterable."""
    install("doctor_ac4_non_iterable_mod", _NON_ITERABLE)

    status = detect_module.detect_auth("claude")

    assert isinstance(status, detect_module.AuthStatus)
    assert status.declaration_consulted is False


def test_declarations_match_catalog_with_rejected_and_healthy_contributions(
    install: Installer, baseline_auth_names: set[str]
) -> None:
    """AC5: with (a) and (c) installed, doctor's key set equals the catalog's."""
    install("doctor_ac5_partial_mod", _PARTIAL_INVALID)
    install("doctor_ac5_healthy_mod", _HEALTHY_CODEX)

    declarations = detect_module.load_auth_declarations()
    catalog_names = _catalog_auth_names()

    assert set(declarations) == catalog_names
    assert catalog_names - baseline_auth_names == {"codex"}
    assert set(declarations) - baseline_auth_names == {"codex"}
