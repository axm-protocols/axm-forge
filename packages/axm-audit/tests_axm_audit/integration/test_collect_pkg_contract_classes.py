"""Split from ``test_shared_helpers_io.py``."""

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality._shared import collect_pkg_contract_classes


@pytest.mark.parametrize(
    ("source_code", "expected_class"),
    [
        pytest.param(
            textwrap.dedent("""
            from typing import Protocol

            class Foo(Protocol):
                def run(self): ...
        """),
            "Foo",
            id="local_protocol",
        ),
        pytest.param(
            textwrap.dedent("""
            from typing import Protocol, runtime_checkable

            @runtime_checkable
            class Baz(Protocol):
                def run(self): ...
        """),
            "Baz",
            id="runtime_checkable_decorator",
        ),
    ],
)
def test_collect_contract_classes_local(
    tmp_path: Path, source_code: str, expected_class: str
) -> None:
    """Protocol classes (plain and runtime_checkable) are collected from local src."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "p.py").write_text(source_code)
    classes = collect_pkg_contract_classes(tmp_path)
    assert expected_class in classes


def test_collect_contract_classes_sibling_package(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    pkg1 = packages / "pkg1"
    pkg2 = packages / "pkg2"
    (pkg1 / "src" / "pkg1").mkdir(parents=True)
    (pkg1 / "src" / "pkg1" / "__init__.py").write_text("")
    (pkg2 / "src" / "pkg2").mkdir(parents=True)
    (pkg2 / "src" / "pkg2" / "__init__.py").write_text("")
    (pkg2 / "src" / "pkg2" / "contracts.py").write_text(
        textwrap.dedent("""
        from abc import ABC

        class Bar(ABC):
            pass
    """)
    )
    classes = collect_pkg_contract_classes(pkg1)
    assert "Bar" in classes
