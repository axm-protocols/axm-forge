from __future__ import annotations

import pytest

from axm_ast.core.analyzer import analyze_package
from axm_ast.core.callers import find_callers
from axm_ast.core.coupling_gaps import find_protocol_coupled

PROTOCOL_SRC = """\
from __future__ import annotations

from typing import Protocol


class Renderer(Protocol):
    def render(self, data: str) -> str:
        ...
"""

IMPL_SRC = """\
from __future__ import annotations


class JsonRenderer:
    def render(self, data: str) -> str:
        return "{}"
"""

CONSUMER_SRC = """\
from __future__ import annotations


def emit(obj) -> str:
    return obj.render("payload")
"""

PLAIN_SRC = """\
from __future__ import annotations


def helper(value: int) -> int:
    return value + 1
"""


@pytest.fixture
def pkg(tmp_path):
    """Build a real package: a Protocol, a shape-only implementor, a shape-only
    consumer, and a plain function — none referencing the Protocol by symbol."""
    root = tmp_path / "shapes"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "protocols.py").write_text(PROTOCOL_SRC)
    (root / "impl.py").write_text(IMPL_SRC)
    (root / "consumer.py").write_text(CONSUMER_SRC)
    (root / "plain.py").write_text(PLAIN_SRC)
    return analyze_package(root)


def test_structural_implementor_returned_with_file_line_why(pkg):
    """AC1: a class implementing the Protocol method by shape (no import or
    reference of the Protocol) is returned, each entry carrying file, line, why."""
    sites = find_protocol_coupled(pkg, "Renderer")
    assert len(sites) >= 1
    impl_sites = [s for s in sites if "impl" in str(s.file)]
    assert impl_sites, sites
    site = impl_sites[0]
    assert "impl" in str(site.file)
    assert isinstance(site.line, int)
    assert site.line > 0
    assert isinstance(site.why, str)
    assert site.why


def test_non_protocol_target_yields_empty_list(pkg):
    """AC2: find_protocol_coupled returns an empty list when the target is not a
    Protocol/ABC member (a plain module function here)."""
    assert find_protocol_coupled(pkg, "helper") == []


def test_structural_consumer_surfaced_though_find_callers_omits_it(pkg):
    """AC3: a consumer that calls the protocol method by shape is surfaced even
    though the reference-based find_callers omits it (it never names Renderer)."""
    callers = find_callers(pkg, "Renderer")
    assert not any("consumer" in str(c.module) for c in callers)
    sites = find_protocol_coupled(pkg, "Renderer")
    assert any("consumer" in str(s.file) for s in sites)
