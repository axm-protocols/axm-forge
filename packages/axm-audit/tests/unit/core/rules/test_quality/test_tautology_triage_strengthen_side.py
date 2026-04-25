"""Unit tests for the 4-series (strengthen-side) triage steps.

Covers AC1-AC9 of AXM-1505: step2 (unique I/O), step3 (unique parametrize),
step4 (boundary literal), step4b (edge-case name), step4c (significant
setup), step4d (mocked SUT contract), step4e (homogeneity in loop/aggregate),
step4f (intentional weakness marker), ordering, and step5 fallthrough.
"""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

import pytest

from axm_audit.core.rules.test_quality.tautology import Finding
from axm_audit.core.rules.test_quality.tautology_triage import triage


def _parse(source: str) -> ast.Module:
    return ast.parse(dedent(source))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _finding(pattern: str = "isinstance_only") -> Finding:
    return Finding(test="test_", line=1, pattern=pattern, detail="")


def _fields(v: object) -> tuple[str, str, str]:
    decision = getattr(v, "decision", None) or getattr(v, "verdict", None)
    step = getattr(v, "step", None)
    reason = getattr(v, "reason", None)
    if decision is None:
        decision, step, reason = v[0], v[1], v[2]  # type: ignore[index]
    return str(decision), str(step), str(reason)


def _call(  # noqa: PLR0913
    source: str,
    target: str,
    *,
    pattern: str = "isinstance_only",
    pkg_symbols: set[str] | None = None,
    contracts: set[str] | None = None,
    source_text: str | None = None,
    tfile: Path | None = None,
) -> object:
    tree = _parse(source)
    func = _func(tree, target)
    return triage(
        _finding(pattern),
        tree=tree,
        func=func,
        enclosing_class=None,
        helpers=[],
        pkg_symbols=pkg_symbols or {"parse", "build", "sut", "run"},
        contracts=contracts or set(),
        test_file=tfile or Path("/tmp/test_mod.py"),
        source_text=source_text if source_text is not None else dedent(source),
    )


@pytest.fixture
def tfile(tmp_path: Path) -> Path:
    f = tmp_path / "test_mod.py"
    f.write_text("")
    return f


# ---------------------------------------------------------------------------
# AC1 — step2_unique_io
# ---------------------------------------------------------------------------


def test_step2_unique_io_strengthens(tfile: Path) -> None:
    src = """
        def test_parse_reads_file(tmp_path):
            f = tmp_path / "x.txt"
            f.write_text("hi")
            with open(f) as fh:
                content = fh.read()
            r = parse(content)
            assert isinstance(r, dict)

        def test_parse_alpha():
            r = parse("alpha_input")
            assert isinstance(r, dict)

        def test_parse_beta():
            r = parse("beta_input")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_reads_file", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step2_unique_io"


# ---------------------------------------------------------------------------
# AC2 — step3_unique_parametrize
# ---------------------------------------------------------------------------


def test_step3_unique_parametrize_strengthens(tfile: Path) -> None:
    src = """
        import pytest

        @pytest.mark.parametrize("val", ["a", "b", "c"])
        def test_parse_many(val):
            r = parse(val)
            assert isinstance(r, dict)

        def test_parse_alpha():
            r = parse("alpha_input")
            assert isinstance(r, dict)

        def test_parse_beta():
            r = parse("beta_input")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_many", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step3_unique_parametrize"


# ---------------------------------------------------------------------------
# AC3 — step4_boundary_literal
# ---------------------------------------------------------------------------


def test_step4_boundary_literal_strengthens(tfile: Path) -> None:
    src = """
        def test_parse_case_a():
            r = parse("")
            assert isinstance(r, dict)

        def test_parse_case_b():
            r = parse("hello")
            assert isinstance(r, dict)

        def test_parse_case_c():
            r = parse("world")
            assert isinstance(r, dict)
    """
    decision, step, reason = _fields(_call(src, "test_parse_case_a", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4_boundary_literal"
    # The reason should mention a literal (the empty string or 'boundary').
    reason_lower = reason.lower()
    assert (
        ("''" in reason)
        or ('""' in reason)
        or ("boundary" in reason_lower)
        or ("literal" in reason_lower)
    )


# ---------------------------------------------------------------------------
# AC4 — step4b_name_edge
# ---------------------------------------------------------------------------


def test_step4b_name_edge_strengthens(tfile: Path) -> None:
    src = """
        def test_parse_empty():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_alpha():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_beta():
            r = parse("input_value")
            x = build(r)
            assert x is not None
    """
    decision, step, _ = _fields(_call(src, "test_parse_empty", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4b_name_edge"


# ---------------------------------------------------------------------------
# AC5 — step4c_significant_setup (P16 extension also covers len_tautology)
# ---------------------------------------------------------------------------


def test_step4c_significant_setup_4_stmts(tfile: Path) -> None:
    src = """
        def test_parse_scenario():
            data = {"k": 1, "v": 2}
            normalized = {k: v for k, v in data.items()}
            payload = [normalized for _ in range(3)]
            r = parse(payload)
            assert isinstance(r, dict)

        def test_parse_other():
            r = parse("other")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_scenario", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4c_significant_setup"


def test_step4c_applies_to_len_tautology(tfile: Path) -> None:
    src = """
        def test_parse_len():
            data = {"k": 1, "v": 2}
            normalized = {k: v for k, v in data.items()}
            payload = [normalized for _ in range(3)]
            r = parse(payload)
            assert len(r) >= 0

        def test_parse_other():
            r = parse("other")
            assert len(r) >= 0
    """
    decision, step, _ = _fields(
        _call(src, "test_parse_len", pattern="len_tautology", tfile=tfile)
    )
    assert decision == "STRENGTHEN"
    assert step == "step4c_significant_setup"


def test_step4c_below_threshold_falls_through(tfile: Path) -> None:
    src = """
        def test_parse_thin():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_other():
            r = parse("input_value")
            assert isinstance(r, dict)
    """
    _, step, _ = _fields(_call(src, "test_parse_thin", tfile=tfile))
    assert step != "step4c_significant_setup"


# ---------------------------------------------------------------------------
# AC6 — step4f_intentional_weakness
# ---------------------------------------------------------------------------


def test_step4f_docstring_marker_strengthens(tfile: Path) -> None:
    src = """
        def test_parse_corrupt_input():
            \"\"\"Doesn't crash on malformed input.\"\"\"
            r = parse("garbage")
            assert isinstance(r, dict)

        def test_parse_other():
            r = parse("garbage")
            assert isinstance(r, dict)
    """
    # We rename the target so that step4b (name-edge) doesn't win first.
    src = src.replace("test_parse_corrupt_input", "test_parse_generic_case")
    decision, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4f_intentional_weakness"


def test_step4f_inline_comment_strengthens(tfile: Path) -> None:
    src_text = (
        "def test_parse_generic_case():\n"
        "    # known limitation: parser is lenient here\n"
        '    r = parse("input_value")\n'
        "    assert isinstance(r, dict)\n"
        "\n"
        "def test_parse_other():\n"
        '    r = parse("input_value")\n'
        "    assert isinstance(r, dict)\n"
    )
    decision, step, _ = _fields(
        _call(
            src_text,
            "test_parse_generic_case",
            tfile=tfile,
            source_text=src_text,
        )
    )
    assert decision == "STRENGTHEN"
    assert step == "step4f_intentional_weakness"


# ---------------------------------------------------------------------------
# AC7 — step4d_mocked_sut_contract
# ---------------------------------------------------------------------------


def test_step4d_mocked_sut_contract(tfile: Path) -> None:
    src = """
        from unittest.mock import patch

        @patch("pkg.dependency")
        def test_parse_generic_case(mock_dep):
            mock_dep.return_value = 42
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_other():
            r = parse("input_value")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4d_mocked_sut_contract"


def test_step4d_requires_sut_return_binding(tfile: Path) -> None:
    # @patch present + isinstance, but isinstance target is NOT assigned from
    # a package SUT call — must not trigger step4d.
    src = """
        from unittest.mock import patch

        @patch("pkg.dependency")
        def test_parse_generic_case(mock_dep):
            mock_dep.return_value = 42
            parse("input_value")
            payload = {"k": 1}
            assert isinstance(payload, dict)

        def test_parse_other():
            r = parse("input_value")
            assert isinstance(r, dict)
    """
    _, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert step != "step4d_mocked_sut_contract"


# ---------------------------------------------------------------------------
# AC8 — step4e_homogeneity_check
# ---------------------------------------------------------------------------


def test_step4e_isinstance_in_for_loop(tfile: Path) -> None:
    src = """
        def test_parse_generic_case():
            items = parse("input_value")
            for x in items:
                assert isinstance(x, int)

        def test_parse_other():
            items = parse("input_value")
            assert isinstance(items, list)
    """
    decision, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4e_homogeneity_check"


def test_step4e_isinstance_in_all_aggregate(tfile: Path) -> None:
    src = """
        def test_parse_generic_case():
            xs = parse("input_value")
            assert all(isinstance(x, int) for x in xs)

        def test_parse_other():
            xs = parse("input_value")
            assert isinstance(xs, list)
    """
    decision, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step4e_homogeneity_check"


def test_step4e_not_in_loop_falls_through(tfile: Path) -> None:
    src = """
        def test_parse_generic_case():
            x = parse("input_value")
            assert isinstance(x, int)

        def test_parse_other():
            x = parse("input_value")
            assert isinstance(x, int)
    """
    _, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert step != "step4e_homogeneity_check"


# ---------------------------------------------------------------------------
# AC9 — step ordering
# ---------------------------------------------------------------------------


def test_ordering_0b_before_2(tfile: Path) -> None:
    # A pure-constructor test surrounded by N pure-constructor siblings must
    # resolve to step0b (DELETE), even if the target happens to also contain
    # a 4-series signal later in the chain.
    src = """
        def test_parse_one():
            r = parse("same_input")
            assert isinstance(r, dict)

        def test_parse_two():
            r = parse("same_input")
            assert isinstance(r, dict)

        def test_parse_three():
            r = parse("same_input")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_one", tfile=tfile))
    assert decision == "DELETE"
    assert step == "step0b_n_copies_constructor"


_ORDERING_CASES = [
    (
        "step2_unique_io",
        "isinstance_only",
        """
        def test_case_a(tmp_path):
            f = tmp_path / "x.txt"
            f.write_text("hi")
            with open(f) as fh:
                content = fh.read()
            r = parse(content)
            assert isinstance(r, dict)

        def test_case_b():
            r = parse("alpha_input")
            assert isinstance(r, dict)

        def test_case_c():
            r = parse("beta_input")
            assert isinstance(r, dict)
        """,
        "test_case_a",
    ),
    (
        "step3_unique_parametrize",
        "isinstance_only",
        """
        import pytest

        @pytest.mark.parametrize("val", ["a", "b"])
        def test_case_a(val):
            r = parse(val)
            assert isinstance(r, dict)

        def test_case_b():
            r = parse("alpha_input")
            assert isinstance(r, dict)

        def test_case_c():
            r = parse("beta_input")
            assert isinstance(r, dict)
        """,
        "test_case_a",
    ),
    (
        "step4_boundary_literal",
        "isinstance_only",
        """
        def test_case_a():
            r = parse("")
            assert isinstance(r, dict)

        def test_case_b():
            r = parse("alpha_input")
            assert isinstance(r, dict)

        def test_case_c():
            r = parse("beta_input")
            assert isinstance(r, dict)
        """,
        "test_case_a",
    ),
    (
        "step4b_name_edge",
        "isinstance_only",
        """
        def test_parse_empty():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_alpha():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_parse_beta():
            r = parse("input_value")
            x = build(r)
            assert x is not None
        """,
        "test_parse_empty",
    ),
    (
        "step4c_significant_setup",
        "isinstance_only",
        """
        def test_parse_generic_case():
            data = {"k": 1, "v": 2}
            normalized = {k: v for k, v in data.items()}
            payload = [normalized for _ in range(3)]
            r = parse(payload)
            assert isinstance(r, dict)

        def test_parse_other():
            r = parse("other")
            assert isinstance(r, dict)
        """,
        "test_parse_generic_case",
    ),
    (
        "step4e_homogeneity_check",
        "isinstance_only",
        """
        def test_parse_generic_case():
            xs = parse("input_value")
            for x in xs:
                assert isinstance(x, int)

        def test_parse_other():
            xs = parse("input_value")
            assert isinstance(xs, list)
        """,
        "test_parse_generic_case",
    ),
]


@pytest.mark.parametrize(
    ("expected_step", "pattern", "source", "target"),
    _ORDERING_CASES,
    ids=[row[0] for row in _ORDERING_CASES],
)
def test_ordering_2_before_3_before_4_etc(
    expected_step: str,
    pattern: str,
    source: str,
    target: str,
    tfile: Path,
) -> None:
    decision, step, _ = _fields(_call(source, target, pattern=pattern, tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == expected_step


# ---------------------------------------------------------------------------
# Step priority — step 1a wins dispatch order
# ---------------------------------------------------------------------------


def test_step_priority_1a_beats_1b(tfile: Path) -> None:
    # Target satisfies step 1a (unique SUT `parse`, not in siblings'
    # dominant calls) AND would also match step 4b (name suggests
    # edge-case via "empty"). Dispatch order is 1a, 2, 3, 4, 4c, 1b, 4b,
    # ... — refactor must keep 1a winning over any later step.
    src = """
        def test_parse_empty():
            r = parse("input_value")
            assert isinstance(r, dict)

        def test_build_alpha():
            r = build("a")
            assert isinstance(r, dict)

        def test_build_beta():
            r = build("b")
            assert isinstance(r, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_empty", tfile=tfile))
    assert decision == "STRENGTHEN"
    assert step == "step1a_unique_fn"


# ---------------------------------------------------------------------------
# step5 fallthrough — truly ambiguous findings stay UNKNOWN
# ---------------------------------------------------------------------------


def test_step5_default_unknown_remains_for_fully_ambiguous(tfile: Path) -> None:
    src = """
        def test_parse_generic_case():
            r = parse("input_value")
            x = build(r)
            assert isinstance(x, dict)

        def test_parse_other():
            r = parse("input_value")
            x = build(r)
            assert isinstance(x, dict)
    """
    decision, step, _ = _fields(_call(src, "test_parse_generic_case", tfile=tfile))
    assert decision == "UNKNOWN"
    assert step == "step5_default_unknown"
