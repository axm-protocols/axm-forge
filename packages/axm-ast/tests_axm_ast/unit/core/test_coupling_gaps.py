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


VALUE_TARGET_SRC = """\
from __future__ import annotations


def verdict(flag: bool) -> str:
    if flag:
        return "pass"
    return "fail"
"""

VALUE_EXACT_SRC = """\
from __future__ import annotations


def gate(status: str) -> bool:
    if status == "pass":
        return True
    return False
"""

VALUE_MEMBER_SRC = """\
from __future__ import annotations


def summarize(status: str) -> str:
    if status in {"pass", "warn"}:
        return "ok"
    return "ko"
"""

VALUE_UNRELATED_SRC = """\
from __future__ import annotations


def choose(fruit: str) -> bool:
    if fruit == "banana":
        return True
    return False
"""


@pytest.fixture
def value_pkg(tmp_path):
    """Build a real package: a target returning the contract literal "pass", an
    exact consumer branching on == "pass", a membership consumer keyed on
    {"pass", "warn"}, and an unrelated site comparing a different literal."""
    root = tmp_path / "verdicts"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "target.py").write_text(VALUE_TARGET_SRC)
    (root / "exact_consumer.py").write_text(VALUE_EXACT_SRC)
    (root / "member_consumer.py").write_text(VALUE_MEMBER_SRC)
    (root / "unrelated.py").write_text(VALUE_UNRELATED_SRC)
    return analyze_package(root)


def test_literal_keyed_site_returned_with_file_line_why(value_pkg):
    """AC1: a site branching on the target's contract literal (== "pass") is
    returned, keyed on that literal, each entry carrying file, line and why."""
    from axm_ast.core.coupling_gaps import find_value_coupled

    sites = find_value_coupled(value_pkg, "verdict")
    assert len(sites) >= 1
    consumer_sites = [s for s in sites if "exact_consumer" in str(s.file)]
    assert consumer_sites, sites
    site = consumer_sites[0]
    assert isinstance(site.line, int)
    assert site.line > 0
    assert isinstance(site.why, str)
    assert site.why


def test_literal_outside_contract_not_flagged(value_pkg):
    """AC2: a site comparing to a literal ("banana") that is not part of the
    target's declared contract is excluded from the result."""
    from axm_ast.core.coupling_gaps import find_value_coupled

    sites = find_value_coupled(value_pkg, "verdict")
    assert not any("unrelated" in str(s.file) for s in sites)


def test_each_site_carries_confidence_label(value_pkg):
    """AC3: with one exact (==) and one heuristic (membership) match, every
    returned site carries a confidence label distinguishing them."""
    from axm_ast.core.coupling_gaps import find_value_coupled

    sites = find_value_coupled(value_pkg, "verdict")
    assert len(sites) >= 1
    assert all(getattr(s, "confidence", None) for s in sites)


GAPS_CALLER_SRC = """\
from __future__ import annotations


def run() -> str:
    return verdict(True)
"""


@pytest.fixture
def gaps_pkg(tmp_path):
    """Build a real package mixing all three coupling kinds for the aggregator:
    a Protocol with a structural implementor (protocol coupling on ``Renderer``),
    a literal-returning ``verdict`` with a branching consumer (value coupling),
    a direct by-name caller of ``verdict`` (reference coupling), and a plain
    uncoupled ``helper``."""
    root = tmp_path / "gaps"
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "protocols.py").write_text(PROTOCOL_SRC)
    (root / "impl.py").write_text(IMPL_SRC)
    (root / "target.py").write_text(VALUE_TARGET_SRC)
    (root / "exact_consumer.py").write_text(VALUE_EXACT_SRC)
    (root / "caller.py").write_text(GAPS_CALLER_SRC)
    (root / "plain.py").write_text(PLAIN_SRC)
    return analyze_package(root)


def test_result_exposes_three_separate_coupling_collections(gaps_pkg):
    """AC1: analyze_coupling_gaps returns a CouplingGapsResult exposing
    reference_coupled, protocol_coupled and value_coupled as three separate,
    populated collections for a batch that triggers all three coupling kinds."""
    from axm_ast.core.coupling_gaps import (
        CouplingGapsResult,
        analyze_coupling_gaps,
    )

    result = analyze_coupling_gaps(gaps_pkg, ["Renderer", "verdict"])
    assert set(result) >= {"reference_coupled", "protocol_coupled", "value_coupled"}
    assert any(result["reference_coupled"].values())
    assert any(result["protocol_coupled"].values())
    assert any(result["value_coupled"].values())
    assert set(CouplingGapsResult.__annotations__) == {
        "reference_coupled",
        "protocol_coupled",
        "value_coupled",
    }


def test_reference_coupled_reaches_parity_with_find_callers(gaps_pkg):
    """AC2: reference_coupled for a target matches the find_callers result set,
    so the reference walk keeps parity with the existing find_callers."""
    from axm_ast.core.coupling_gaps import analyze_coupling_gaps

    result = analyze_coupling_gaps(gaps_pkg, ["verdict"])
    expected = find_callers(gaps_pkg, "verdict")
    assert expected  # caller.py names verdict directly
    got = {(c.module, c.line, c.symbol) for c in result["reference_coupled"]["verdict"]}
    exp = {(c.module, c.line, c.symbol) for c in expected}
    assert got == exp


def test_batch_of_symbols_is_aggregated_per_input(gaps_pkg):
    """AC3: analyze_coupling_gaps accepts a list of symbols and aggregates
    results per input symbol, mirroring ast_impact's symbols batching."""
    from axm_ast.core.coupling_gaps import analyze_coupling_gaps

    result = analyze_coupling_gaps(gaps_pkg, ["verdict", "helper"])
    assert set(result["reference_coupled"]) == {"verdict", "helper"}
    assert set(result["protocol_coupled"]) == {"verdict", "helper"}
    assert set(result["value_coupled"]) == {"verdict", "helper"}
