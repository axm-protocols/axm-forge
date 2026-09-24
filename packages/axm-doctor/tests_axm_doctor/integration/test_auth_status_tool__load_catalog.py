"""Integration: auth_status relays axm-vault catalog rejections.

Each test installs a real distribution (module + dist-info) on ``tmp_path``
and lets ``importlib.metadata`` discover its ``axm.credentials`` entry
points: the real vault discovery path is exercised, nothing is mocked.
"""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from axm_vault import load_catalog

from axm_doctor.tools import AuthStatusTool

pytestmark = pytest.mark.integration

Installer = Callable[[str, str, dict[str, str]], None]


def _clear_catalog_cache() -> None:
    cache_clear = getattr(load_catalog, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
    importlib.invalidate_caches()


@pytest.fixture
def install_contribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Installer]:
    """Install a real distribution declaring ``axm.credentials`` entry points."""
    installed_modules: list[str] = []

    def _install(module: str, source: str, entries: dict[str, str]) -> None:
        (tmp_path / f"{module}.py").write_text(textwrap.dedent(source))
        dist_info = tmp_path / f"{module}-0.0.0.dist-info"
        dist_info.mkdir()
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {module}\nVersion: 0.0.0\n"
        )
        lines = "\n".join(f"{name} = {target}" for name, target in entries.items())
        (dist_info / "entry_points.txt").write_text(f"[axm.credentials]\n{lines}\n")
        installed_modules.append(module)
        monkeypatch.syspath_prepend(str(tmp_path))
        _clear_catalog_cache()

    _clear_catalog_cache()
    yield _install
    for module in installed_modules:
        sys.modules.pop(module, None)
    _clear_catalog_cache()


_EMPTY_LOGIN_PROVIDER = """
from axm_vault.auth import AuthDependencySpec, AuthStatus


class _Source:
    def status(self):
        return AuthStatus.DISCONNECTED


def provide():
    AuthDependencySpec(name="doctor_tool", source=_Source(), login_command="")
    return []
"""

_RAISING_PROVIDER = """
def provide():
    raise RuntimeError("doctor provider exploded")
"""


def test_empty_login_command_contribution_is_reported_as_rejection(
    install_contribution: Installer,
) -> None:
    """AC1: an empty login_command contribution surfaces in data['rejections']."""
    install_contribution(
        "doctor_empty_login_mod",
        _EMPTY_LOGIN_PROVIDER,
        {"doctor_empty_login": "doctor_empty_login_mod:provide"},
    )

    result = AuthStatusTool().execute()

    assert result.success is True
    rejections = result.data["rejections"]
    matching = [e for e in rejections if e["entry_point"] == "doctor_empty_login"]
    assert matching
    assert any("login_command" in e["reason"] for e in matching)


def test_rejections_match_vault_catalog_exactly(
    install_contribution: Installer,
) -> None:
    """AC2: rejections are relayed verbatim from load_catalog().rejections()."""
    install_contribution(
        "doctor_two_rejections_mod",
        _RAISING_PROVIDER,
        {
            "doctor_broken_load": "doctor_two_rejections_mod:missing_attribute",
            "doctor_raising_provider": "doctor_two_rejections_mod:provide",
        },
    )

    result = AuthStatusTool().execute()

    assert result.success is True
    relayed = {(e["entry_point"], e["reason"]) for e in result.data["rejections"]}
    expected = {(r.entry_point, r.reason) for r in load_catalog().rejections()}
    assert relayed == expected
    names = {name for name, _ in relayed}
    assert {"doctor_broken_load", "doctor_raising_provider"} <= names


def test_text_lists_rejected_entry_point_on_dedicated_line(
    install_contribution: Installer,
) -> None:
    """AC3: the text names the rejected entry point on a dedicated line."""
    install_contribution(
        "doctor_text_rejection_mod",
        _RAISING_PROVIDER,
        {"doctor_raising_provider": "doctor_text_rejection_mod:provide"},
    )

    result = AuthStatusTool().execute()

    assert result.success is True
    assert result.text is not None
    assert any(
        line.startswith("Rejected credential contributions:")
        and "doctor_raising_provider" in line
        for line in result.text.splitlines()
    )
