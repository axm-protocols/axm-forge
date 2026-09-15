from __future__ import annotations

import importlib
import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.integration
def test_declared_probe_url_is_a_route_the_server_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The advertised probe path is served by the app, not merely well-formed.

    Nothing tied the descriptor's URL to the routes the server registers, and
    the two drifted: the descriptor published the bare origin while the only
    liveness route is ``/health``. A supervisor polling that URL got a 404,
    read it as unresponsive, and reported a live server as stopped — then its
    caller started a second one, which died on the address already in use.

    So this asserts the *agreement*, by taking the path from the descriptor and
    looking it up among the routes the application actually exposes. Comparing
    the URL to a literal here would only add a fourth copy of the string, which
    is what let the drift happen in the first place.
    """
    monkeypatch.setenv("AXM_PROFILE", "production")
    from urllib.parse import urlsplit

    from axm_mcp.daemon import daemon_descriptor
    from axm_mcp.mcp_app import mcp

    service = next(iter(daemon_descriptor().values()))
    probe = service["probe"]
    assert isinstance(probe, Mapping)
    declared = urlsplit(str(probe["url"])).path

    #: Importing `server` is what registers the route on the shared instance:
    #: the decorator runs at import time.
    importlib.import_module("axm_mcp.server")
    served = {
        getattr(route, "path", None) for route in mcp.streamable_http_app().routes
    }

    assert declared in served, (
        f"the descriptor advertises {declared!r}, which the server does not "
        f"serve; it exposes {sorted(path for path in served if path)}"
    )


@pytest.mark.integration
def test_declared_daemon_entry_point_is_importable_and_equivalent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC5: declare one importable daemon target matching the public function."""
    monkeypatch.setenv("AXM_PROFILE", "production")
    package_root = Path(__file__).parents[2]
    with (package_root / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)

    entries = pyproject["project"]["entry-points"]["axm.daemons"]
    assert entries == {"axm-mcp": "axm_mcp.daemon:daemon_descriptor"}

    target = next(iter(entries.values()))
    module_name, attribute_name = target.split(":", maxsplit=1)
    declared_module: ModuleType = importlib.import_module(module_name)
    declared_descriptor = getattr(declared_module, attribute_name)
    public_module: ModuleType = importlib.import_module("axm_mcp.daemon")

    assert declared_descriptor() == public_module.daemon_descriptor()
