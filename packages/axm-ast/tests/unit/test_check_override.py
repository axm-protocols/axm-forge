"""Split from ``test_dead_code.py``."""

import pytest

from axm_ast.core.dead_code import _check_override
from tests.unit._helpers import _cls, _method, _no_callers, _override_mod, _override_pkg


def test_dunder_override_external_base_presumed_live() -> None:
    """Dunder method overriding external base — presumed live (not private)."""
    child = _cls(
        "MyModel",
        bases=["ExternalBase"],
        methods=[_method("__init__", 5)],
    )
    pkg = _override_pkg(modules=[_override_mod(classes=[child])])

    assert _check_override("__init__", child, pkg) is True


def test_external_base_truly_dead_method() -> None:
    """All bases external, brand-new method — acceptable false negative."""
    child = _cls(
        "Foo",
        bases=["ExternalBase"],
        methods=[_method("totally_new_method", 10)],
    )
    pkg = _override_pkg(modules=[_override_mod(classes=[child])])

    assert _check_override("totally_new_method", child, pkg) is True


class TestCheckOverrideExternal:
    """_check_override must return True when the base class is external."""

    def test_override_external_base_not_dead(self) -> None:
        """Class inheriting ExternalBase (not in package) with do_GET."""
        handler = _cls("MyHandler", bases=["ExternalBase"], methods=[_method("do_GET")])
        pkg = _override_pkg(modules=[_override_mod(classes=[handler])])

        assert _check_override("do_GET", handler, pkg) is True

    def test_override_external_base_log_message(self) -> None:
        """Class inheriting ExternalBase with log_message."""
        handler = _cls(
            "MyHandler", bases=["ExternalBase"], methods=[_method("log_message")]
        )
        pkg = _override_pkg(modules=[_override_mod(classes=[handler])])

        assert _check_override("log_message", handler, pkg) is True

    def test_override_inpackage_base_still_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Class inheriting in-package Base with uncalled method — method IS flagged."""
        base = _cls("Base", bases=[], methods=[_method("process")])
        child = _cls("Child", bases=["Base"], methods=[_method("process")])
        pkg = _override_pkg(modules=[_override_mod(classes=[base, child])])

        monkeypatch.setattr("axm_ast.core.callers.find_callers", _no_callers)

        assert _check_override("process", child, pkg) is False
