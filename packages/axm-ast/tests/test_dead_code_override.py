from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from axm_ast.core.dead_code import _check_override, _scan_methods

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _method(name: str, line_start: int = 1) -> SimpleNamespace:
    return SimpleNamespace(name=name, line_start=line_start)


def _cls(
    name: str, bases: list[str], methods: list[SimpleNamespace] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(name=name, bases=bases, methods=methods or [])


def _mod(classes: list[SimpleNamespace], path: str = "mod.py") -> SimpleNamespace:
    return SimpleNamespace(classes=classes, path=path)


def _pkg(modules: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(modules=modules)


def _ctx(**overrides: Any) -> SimpleNamespace:
    defaults: dict[str, Any] = {
        "entry_points": set(),
        "all_refs": set(),
        "extra_pkg": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _no_callers(_pkg_arg: Any, _name: str) -> list[Any]:
    return []


# ---------------------------------------------------------------------------
# Unit tests — _check_override
# ---------------------------------------------------------------------------


class TestCheckOverrideExternal:
    """_check_override must return True when the base class is external."""

    def test_override_external_base_not_dead(self) -> None:
        """Class inheriting ExternalBase (not in package) with do_GET."""
        handler = _cls("MyHandler", bases=["ExternalBase"], methods=[_method("do_GET")])
        pkg = _pkg(modules=[_mod(classes=[handler])])

        assert _check_override("do_GET", handler, pkg) is True  # type: ignore[arg-type]

    def test_override_external_base_log_message(self) -> None:
        """Class inheriting ExternalBase with log_message."""
        handler = _cls(
            "MyHandler", bases=["ExternalBase"], methods=[_method("log_message")]
        )
        pkg = _pkg(modules=[_mod(classes=[handler])])

        assert _check_override("log_message", handler, pkg) is True  # type: ignore[arg-type]

    def test_override_inpackage_base_still_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Class inheriting in-package Base with uncalled method — method IS flagged."""
        base = _cls("Base", bases=[], methods=[_method("process")])
        child = _cls("Child", bases=["Base"], methods=[_method("process")])
        pkg = _pkg(modules=[_mod(classes=[base, child])])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)

        assert _check_override("process", child, pkg) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Functional tests — _scan_methods end-to-end
# ---------------------------------------------------------------------------


class TestFunctionalOverride:
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
        mod = _mod(classes=[handler], path="handlers.py")
        pkg = _pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(handler, mod, pkg, _ctx())  # type: ignore[arg-type]
        dead_names = {d.name for d in dead}

        assert "MyHandler.do_GET" not in dead_names
        assert "MyHandler.log_message" not in dead_names

    def test_thread_run_not_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Thread subclass with run() override — not flagged."""
        worker = _cls("Worker", bases=["Thread"], methods=[_method("run", 5)])
        mod = _mod(classes=[worker], path="workers.py")
        pkg = _pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(worker, mod, pkg, _ctx())  # type: ignore[arg-type]
        dead_names = {d.name for d in dead}

        assert "Worker.run" not in dead_names


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestOverrideEdgeCases:
    """Boundary conditions for external-base override heuristic."""

    def test_mixed_bases_external_method_exempted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In-pkg + external base — method only on external is exempted."""
        in_pkg_base = _cls("InPkgBase", bases=[], methods=[])
        child = _cls(
            "Foo",
            bases=["InPkgBase", "ExternalBase"],
            methods=[_method("external_method", 10)],
        )
        mod = _mod(classes=[in_pkg_base, child], path="mixed.py")
        pkg = _pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(child, mod, pkg, _ctx())  # type: ignore[arg-type]
        dead_names = {d.name for d in dead}

        assert "Foo.external_method" not in dead_names

    def test_private_method_on_external_base_still_flagged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Private method on external base \u2014 still flagged."""
        child = _cls(
            "Foo",
            bases=["ExternalBase"],
            methods=[_method("_internal_helper", 10)],
        )
        mod = _mod(classes=[child], path="priv.py")
        pkg = _pkg(modules=[mod])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)
        monkeypatch.setattr(
            "axm_ast.core.dead_code._is_exempt_function", lambda *a, **kw: False
        )

        dead = _scan_methods(child, mod, pkg, _ctx())  # type: ignore[arg-type]
        dead_names = {d.name for d in dead}

        assert "Foo._internal_helper" in dead_names

    def test_external_base_truly_dead_method(self) -> None:
        """All bases external, brand-new method — acceptable false negative."""
        child = _cls(
            "Foo",
            bases=["ExternalBase"],
            methods=[_method("totally_new_method", 10)],
        )
        pkg = _pkg(modules=[_mod(classes=[child])])

        # Conservative heuristic: public method + external base → exempt (True).
        # This is an acceptable false negative per spec.
        assert _check_override("totally_new_method", child, pkg) is True  # type: ignore[arg-type]
