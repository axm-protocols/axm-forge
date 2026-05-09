from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import (
    DuplicateTestsRule,
)
from axm_audit.models.results import Severity


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    return tmp_path


def _cluster_signals(result: Any) -> list[str]:
    return [c["signal"] for c in result.metadata["clusters"]]


def test_s1_same_sut_same_asserts_clusters(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_parse_one():
            result = parse(1)
            assert result == 1
            assert result > 0

        def test_parse_two():
            result = parse(2)
            assert result == 1
            assert result > 0
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert len(result.metadata["clusters"]) == 1
    assert signals == ["signal1_call_assert"]


def test_s2_cross_file_same_name_high_similarity(project: Path) -> None:
    body = """
        def test_x():
            result = compute(1, 2)
            assert result == 3
            assert isinstance(result, int)
    """
    _write(project / "tests" / "test_a.py", body)
    _write(project / "tests" / "test_b.py", body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    clusters = result.metadata["clusters"]
    s2 = [c for c in clusters if c["signal"] == "signal2_cross_file_name"]
    assert s2, f"expected signal2_cross_file_name in {clusters}"
    assert s2[0]["similarity"] >= 0.95


def test_s3_intra_file_similarity(project: Path) -> None:
    # Same public SUT set on both sides so P7 (distinct-SUT rescue)
    # does not fire.  A kwarg-only divergence on the asserted call
    # breaks the S1 ``call_sig`` match (kwargs are part of the sig)
    # while keeping ``stmt_set`` Jaccard ≥ threshold, leaving S3 as
    # the only signal that can cluster the pair.
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_alpha():
            x = foo(1)
            y = bar(x)
            z = baz(y, mode="strict")
            assert z == 5

        def test_gamma():
            x = foo(1)
            y = bar(x)
            z = baz(y, mode="loose")
            assert z == 5
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "signal3_intra_file_similarity" in signals


def test_p1_distinct_literals_rescues_s1(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_parse_one():
            result = parse("foo")
            assert result == "alpha"

        def test_parse_two():
            result = parse("bar")
            assert result == "beta"
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert signals == ["ambiguous_distinct_literals"]


def test_p1_single_literal_diff_does_not_rescue(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_parse_one():
            result = parse("foo")
            assert result == 1

        def test_parse_two():
            result = parse("bar")
            assert result == 1
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert signals == ["signal1_call_assert"]


def test_p1_docstring_diff_ignored(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        '''
        def test_parse_one():
            """First description."""
            result = parse(1)
            assert result == 1

        def test_parse_two():
            """Second description."""
            result = parse(1)
            assert result == 1
        ''',
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_distinct_literals" not in signals
    assert signals == ["signal1_call_assert"]


def test_p2_patch_context_rescues(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        from unittest.mock import patch

        def test_parse_one():
            with patch("mod.dep"):
                result = parse(1)
                assert result == 1

        def test_parse_two():
            result = parse(1)
            assert result == 1
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_patch_context" in signals


def test_p2_mocker_patch_asymmetry(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_parse_one(mocker):
            mocker.patch("mod.dep")
            result = parse(1)
            assert result == 1

        def test_parse_two():
            result = parse(1)
            assert result == 1
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_patch_context" in signals


def test_p3_cross_file_template_pair_rescues(project: Path) -> None:
    body = """
        def test_parse():
            result = run(1)
            assert result == 1
    """
    _write(project / "tests" / "test_json_parser.py", body)
    _write(project / "tests" / "test_yaml_parser.py", body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_template_pair" in signals


_P3_SHORT_BODY = """
    def test_parse():
        result = run(1)
        assert result == 1
"""

_P3_LONG_BODY = """
    def test_parse():
        a = step_one(1)
        b = step_two(a)
        c = step_three(b)
        d = step_four(c)
        e = step_five(d)
        f = step_six(e)
        assert f == 0
"""

_P4_LARGE_BODIES = """
    def test_alpha():
        a = f1(1)
        b = f2(a)
        c = f3(b)
        d = f4(c)
        e = f5(d)
        g = f6(e)
        h = f7(g)
        i = f8(h)
        j = f9(i)
        assert j == 0

    def test_beta():
        a = f1(2)
        b = f2(a)
        c = f3(b)
        d = f4(c)
        e = f5(d)
        g = f6(e)
        h = f7(g)
        i = f8(h)
        assert i == 0
"""

_P6_SAME_COUNT = """
    def test_one():
        result = compute(1)
        assert result == 1

    def test_two():
        result = compute(2)
        assert result == 1
"""

_P6_UNDERSCORE_HELPER = """
    def test_alpha():
        checks = [_make_check(80)]
        result = quality_score(checks)
        assert result == 80

    def test_beta():
        checks = [_make_check(80), _make_check(60), _make_check(100)]
        result = quality_score(checks)
        assert result == 80
"""

_P6_BUILTIN = """
    def test_alpha(tmp_path):
        (tmp_path / "a").mkdir()
        result = scan(tmp_path)
        assert result == "ok"

    def test_beta(tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "c").mkdir()
        result = scan(tmp_path)
        assert result == "ok"
"""

_P7_SUBSET = """
    def test_alpha():
        result = parse("foo")
        assert result == "alpha"

    def test_beta():
        warmup()
        result = parse("bar")
        assert result == "beta"
"""


@pytest.mark.parametrize(
    ("files", "absent_signal"),
    [
        pytest.param(
            [("test_a.py", _P3_SHORT_BODY), ("test_b.py", _P3_SHORT_BODY)],
            "ambiguous_template_pair",
            id="p3_token_too_short",
        ),
        pytest.param(
            [
                ("test_json_parser.py", _P3_LONG_BODY),
                ("test_yaml_parser.py", _P3_LONG_BODY),
            ],
            "ambiguous_template_pair",
            id="p3_long_body",
        ),
        pytest.param(
            [("test_mod.py", _P4_LARGE_BODIES)],
            "ambiguous_body_size",
            id="p4_large_bodies",
        ),
        pytest.param(
            [("test_mod.py", _P6_SAME_COUNT)],
            "ambiguous_call_multiplicity",
            id="p6_same_count",
        ),
        pytest.param(
            [("test_mod.py", _P6_UNDERSCORE_HELPER)],
            "ambiguous_call_multiplicity",
            id="p6_underscore_helper",
        ),
        pytest.param(
            [("test_mod.py", _P6_BUILTIN)],
            "ambiguous_call_multiplicity",
            id="p6_builtin",
        ),
        pytest.param(
            [("test_mod.py", _P7_SUBSET)],
            "ambiguous_distinct_sut",
            id="p7_subset",
        ),
    ],
)
def test_guard_does_not_rescue(
    project: Path, files: list[tuple[str, str]], absent_signal: str
) -> None:
    for filename, body in files:
        _write(project / "tests" / filename, body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert absent_signal not in signals


def test_p4_intra_file_body_size_delta_rescues(project: Path) -> None:
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_alpha():
            x = foo(1)
            y = bar(x)
            z = baz(y)
            w = qux(z)
            assert w == 5

        def test_beta():
            x = foo(2)
            y = bar(x)
            z = baz(y)
            assert z == 5
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_body_size" in signals


def test_p6_call_multiplicity_rescues_s1(project: Path) -> None:
    """Common public SUT called once vs twice -> demoted to call_multiplicity."""
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_applies_shading():
            cell = make_cell()
            shade_cell(cell, "RED")
            assert cell.color == "RED"

        def test_replaces_existing_shading():
            cell = make_cell()
            shade_cell(cell, "RED")
            shade_cell(cell, "BLUE")
            assert cell.color == "BLUE"
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_call_multiplicity" in signals


def test_p7_distinct_sut_rescues_s3(project: Path) -> None:
    """P7 — same skeleton + side-effecting distinct SUTs ≠ duplicates.

    Reproduit le faux positif `atd-reporter` cluster #15: deux smoke
    tests dont le SUT (``fill_highlight`` vs ``_shift_ppr_tracking_table``)
    n'apparaît pas sur la chaîne d'asserts (side-effect), donc
    ``call_sig`` capte le builder de fixture et S1 ne déclenche pas; S3
    clusterise par similarité brute.  P7 doit demoter en
    ``ambiguous_distinct_sut``.
    """
    _write(
        project / "tests" / "test_mod.py",
        """
        def test_no_table_no_crash():
            doc = Document()
            fill_highlight(doc, "data")
            assert len(doc.tables) == 0

        def test_no_ppr_table_no_crash():
            cell = _make_cell()
            _shift_ppr_tracking_table(cell, "data")
            assert len(cell.tables) == 0
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert "ambiguous_distinct_sut" in signals
    assert "signal3_intra_file_similarity" not in signals


def test_metadata_bucket_counts_classifications(project: Path) -> None:
    _write(
        project / "tests" / "test_clustered.py",
        """
        def test_c1():
            result = parse(1)
            assert result == 1
            assert result > 0

        def test_c2():
            result = parse(2)
            assert result == 1
            assert result > 0
        """,
    )
    _write(
        project / "tests" / "test_ambig.py",
        """
        def test_a1():
            result = parse("foo")
            assert result == "alpha"

        def test_a2():
            result = parse("bar")
            assert result == "beta"
        """,
    )
    _write(
        project / "tests" / "test_unique.py",
        """
        def test_lonely():
            assert len([1, 2, 3]) == 3
        """,
    )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    assert "buckets" not in result.metadata
    counts = result.metadata["bucket_counts"]
    assert set(counts.keys()) == {"CLUSTERED", "AMBIGUOUS", "UNIQUE"}
    assert counts["CLUSTERED"] == 2
    assert counts["AMBIGUOUS"] == 2
    assert counts["UNIQUE"] == 1

    # Cluster members must use the slim shape: file/name/line, no call_sig.
    for cluster in result.metadata["clusters"]:
        assert "members" in cluster
        for member in cluster["members"]:
            assert set(member.keys()) == {"file", "name", "line"}


def test_severity_warning_and_scoring(project: Path) -> None:
    for i in range(3):
        _write(
            project / "tests" / f"test_clu_{i}.py",
            f"""
            def test_c{i}_1():
                result = sut_{i}(1)
                assert result == {i}
                assert result >= 0

            def test_c{i}_2():
                result = sut_{i}(2)
                assert result == {i}
                assert result >= 0
            """,
        )
    for j in range(2):
        _write(
            project / "tests" / f"test_amb_{j}.py",
            f"""
            def test_a{j}_1():
                result = sut_amb_{j}("foo")
                assert result == "alpha"

            def test_a{j}_2():
                result = sut_amb_{j}("bar")
                assert result == "beta"
            """,
        )
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    assert result.severity == Severity.WARNING
    assert result.score == 85


def test_empty_tests_returns_pass(tmp_path: Path) -> None:
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(tmp_path)
    assert result.passed is True
    assert result.score == 100


def _has_pair(clusters: list[dict[str, Any]], names: set[str]) -> bool:
    for c in clusters:
        cluster_names = {t["name"] for t in c["tests"]}
        if names.issubset(cluster_names):
            return True
    return False


def _find_pair(
    clusters: list[dict[str, Any]], names: set[str]
) -> dict[str, Any] | None:
    for c in clusters:
        cluster_names = {t["name"] for t in c["tests"]}
        if names.issubset(cluster_names):
            return c
    return None


def test_distinct_self_attr_sut_not_clustered(project: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setUp(self):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    _write(project / "tests" / "test_a.py", body)

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})


def test_same_self_attr_sut_still_clustered(project: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setUp(self):\n"
        "        self.parser = Parser()\n"
        "    def test_first(self):\n"
        "        result = self.parser.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser.run()\n"
        "        assert result == 1\n"
    )
    _write(project / "tests" / "test_a.py", body)

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


def test_setup_method_variant(project: Path) -> None:
    body = (
        "class TestX:\n"
        "    def setup_method(self, method):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    _write(project / "tests" / "test_a.py", body)

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})


def test_pytest_fixture_class_attr(project: Path) -> None:
    body = (
        "import pytest\n\n"
        "class TestX:\n"
        "    @pytest.fixture(autouse=True)\n"
        "    def _setup(self):\n"
        "        self.parser_a = ParserA()\n"
        "        self.parser_b = ParserB()\n"
        "    def test_first(self):\n"
        "        result = self.parser_a.run()\n"
        "        assert result == 1\n"
        "    def test_second(self):\n"
        "        result = self.parser_b.run()\n"
        "        assert result == 1\n"
    )
    _write(project / "tests" / "test_a.py", body)

    result = DuplicateTestsRule().check(project)

    assert not _has_pair(result.metadata["clusters"], {"test_first", "test_second"})
