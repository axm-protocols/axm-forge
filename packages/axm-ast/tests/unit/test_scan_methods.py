"""Split from ``test_dead_code.py``."""

from typing import Any

import pytest

from axm_ast.core.dead_code import _scan_methods
from tests.unit._helpers import _cls, _method, _no_callers, _override_mod, _override_pkg


def _override_ctx(**overrides: Any) -> Any:
    from types import SimpleNamespace

    defaults: dict[str, Any] = {
        "entry_points": set(),
        "all_refs": set(),
        "extra_pkg": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_mixed_bases_external_method_exempted(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-pkg + external base — method only on external is exempted."""
    in_pkg_base = _cls("InPkgBase", bases=[], methods=[])
    child = _cls(
        "Foo",
        bases=["InPkgBase", "ExternalBase"],
        methods=[_method("external_method", 10)],
    )
    mod = _override_mod(classes=[in_pkg_base, child], path="mixed.py")
    pkg = _override_pkg(modules=[mod])

    monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
    monkeypatch.setattr(
        "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
    )

    dead = _scan_methods(child, mod, pkg, _override_ctx())
    dead_names = {d.name for d in dead}

    assert "Foo.external_method" not in dead_names


def test_private_method_on_external_base_still_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Private method on external base — still flagged."""
    child = _cls(
        "Foo",
        bases=["ExternalBase"],
        methods=[_method("_internal_helper", 10)],
    )
    mod = _override_mod(classes=[child], path="priv.py")
    pkg = _override_pkg(modules=[mod])

    monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
    monkeypatch.setattr(
        "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
    )

    dead = _scan_methods(child, mod, pkg, _override_ctx())
    dead_names = {d.name for d in dead}

    assert "Foo._internal_helper" in dead_names


class TestScanMethodsExternalOverride:
    """_scan_methods must not flag methods overriding external bases."""

    def test_http_handler_methods_not_dead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BaseHTTPRequestHandler subclass — do_GET and log_message not flagged."""
        handler = _cls(
            "MyHandler",
            bases=["BaseHTTPRequestHandler"],
            methods=[_method("do_GET", 10), _method("log_message", 20)],
        )
        mod = _override_mod(classes=[handler], path="handlers.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(handler, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "MyHandler.do_GET" not in dead_names
        assert "MyHandler.log_message" not in dead_names

    def test_thread_run_not_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Thread subclass with run() override — not flagged."""
        worker = _cls("Worker", bases=["Thread"], methods=[_method("run", 5)])
        mod = _override_mod(classes=[worker], path="workers.py")
        pkg = _override_pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(worker, mod, pkg, _override_ctx())
        dead_names = {d.name for d in dead}

        assert "Worker.run" not in dead_names
