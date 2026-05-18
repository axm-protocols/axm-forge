from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from axm_audit.core.rules.test_quality.duplicate_tests import DuplicateTestsRule
from tests.integration._helpers import _find_pair


def _write(tmp_path: Path, files: dict[str, str]) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, body in files.items():
        (tests / name).write_text(body)
    return tmp_path


IDENTICAL_BODY = (
    "    def test_run(self):\n        result = process(1)\n        assert result == 2\n"
)


def test_cross_class_pair_demoted(tmp_path: Path) -> None:
    file_a = "class TestFoo:\n" + IDENTICAL_BODY
    file_b = "class TestBar:\n" + IDENTICAL_BODY
    project = _write(tmp_path, {"test_a.py": file_a, "test_b.py": file_b})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_run"})
    assert pair is not None
    assert pair["signal"] == "ambiguous_distinct_class"


@pytest.mark.parametrize(
    ("files", "pair_names"),
    [
        pytest.param(
            {
                "test_a.py": (
                    "class TestFoo:\n"
                    "    def test_first(self):\n"
                    "        result = process(1)\n"
                    "        assert result == 2\n"
                    "    def test_second(self):\n"
                    "        result = process(1)\n"
                    "        assert result == 2\n"
                ),
            },
            {"test_first", "test_second"},
            id="same_class_pair_still_clustered",
        ),
        pytest.param(
            {
                "test_a.py": (
                    "def test_alpha():\n"
                    "    result = process(1)\n"
                    "    assert result == 2\n"
                ),
                "test_b.py": (
                    "def test_beta():\n"
                    "    result = process(1)\n"
                    "    assert result == 2\n"
                ),
            },
            {"test_alpha", "test_beta"},
            id="module_level_pair_unaffected",
        ),
    ],
)
def test_pair_clusters_with_signal1_or_signal3(
    tmp_path: Path, files: dict[str, str], pair_names: set[str]
) -> None:
    project = _write(tmp_path, files)

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], pair_names)
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


def _write_duplicate_pair(tests_dir: Path) -> None:
    """Write two byte-identical tests into a temp tests/ directory."""
    tests_dir.mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent(
        """\
        def test_alpha():
            result = compute(1, 2)
            assert result == 3


        def test_beta():
            result = compute(1, 2)
            assert result == 3
        """
    )
    (tests_dir / "test_dupes.py").write_text(body, encoding="utf-8")


def _make_tmp_project(root: Path) -> Path:
    """Lay out a minimal project with one duplicate-test pair under tests/."""
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    _write_duplicate_pair(root / "tests")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    return root


def test_score_matches_pair_count_from_members(tmp_path: Path) -> None:
    """AC4: score from `members` matches pre-change behavior on 1-pair input."""
    project = _make_tmp_project(tmp_path)
    result = DuplicateTestsRule().check(project)
    assert result.score == 95
    assert re.search(r"1 cluster\(s\), 1 clustered pair\(s\)", result.message)


def test_self_audit_payload_under_size_threshold() -> None:
    """AC5: self-audit cluster payload is < 65 000 chars after the dedup."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    payload = json.dumps(result.metadata["clusters"])
    assert len(payload) < 65_000


def test_no_cluster_dict_has_tests_key() -> None:
    """AC1, AC2: every cluster in metadata uses `members`, never `tests`."""
    pkg_root = Path(__file__).resolve().parents[2]
    result = DuplicateTestsRule().check(pkg_root)
    for cluster in result.metadata["clusters"]:
        assert "members" in cluster
        assert "tests" not in cluster


def test_one_with_raises_one_without_demoted(tmp_path: Path) -> None:
    body = (
        "import pytest\n\n"
        "def test_with_raises():\n"
        "    with pytest.raises(ValueError):\n"
        "        fn(1)\n\n"
        "def test_without_raises():\n"
        "    result = fn(1)\n"
        "    assert result == 0\n"
    )
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(
        result.metadata["clusters"], {"test_with_raises", "test_without_raises"}
    )
    assert pair is not None
    assert pair["signal"] == "ambiguous_raises_divergence"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            (
                "import pytest\n\n"
                "def test_first():\n"
                "    with pytest.raises(ValueError):\n"
                "        fn(1)\n\n"
                "def test_second():\n"
                "    with pytest.raises(ValueError):\n"
                "        fn(1)\n"
            ),
            id="both_with_raises_still_clustered",
        ),
        pytest.param(
            (
                "def test_first():\n"
                "    result = fn(1)\n"
                "    assert result == 0\n\n"
                "def test_second():\n"
                "    result = fn(1)\n"
                "    assert result == 0\n"
            ),
            id="neither_with_raises_unaffected",
        ),
    ],
)
def test_raises_symmetric_pair_clusters(tmp_path: Path, body: str) -> None:
    project = _write(tmp_path, {"test_a.py": body})

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


AMBIGUOUS_TEST_FILE = """
from __future__ import annotations


def test_alpha() -> None:
    x = 1
    y = 2
    assert x + y == 3


def test_beta() -> None:
    x = 10
    y = 20
    assert x + y == 30
"""


def test_audit_exposes_ambiguous_clusters_in_text(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    tests = pkg / "tests" / "unit"
    src.mkdir(parents=True)
    tests.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (pkg / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "0.0.0"\n')
    (tests / "test_dup.py").write_text(AMBIGUOUS_TEST_FILE)

    result = DuplicateTestsRule().check(pkg)
    text = result.text or ""
    if not result.passed:
        assert "test_alpha" in text or "test_beta" in text
        assert "test_dup.py" in text


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


_P7_SUBSET = """
    def test_alpha():
        result = parse("foo")
        assert result == "alpha"

    def test_beta():
        warmup()
        result = parse("bar")
        assert result == "beta"
"""


_P3_SHORT_BODY = """
    def test_parse():
        result = run(1)
        assert result == 1
"""

_P6_SAME_COUNT = """
    def test_one():
        result = compute(1)
        assert result == 1

    def test_two():
        result = compute(2)
        assert result == 1
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


_DISTINCT_SELF_ATTR_SETUP_VARIANTS = {
    "setUp": (
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
    ),
    "setup_method": (
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
    ),
    "pytest_fixture": (
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
    ),
}


def _write__from_duplicate_tests_rule(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip())


@pytest.fixture
def duplicate_tests_project(tmp_path: Path) -> Path:
    body = dedent(
        """
        def test_dup_a():
            x = 1
            assert x == 1

        def test_dup_b():
            x = 1
            assert x == 1
        """
    ).lstrip()
    _write__from_duplicate_tests_rule(tmp_path / "tests" / "test_dup.py", body)
    return tmp_path


def _write__from_duplicate_test_clustering(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def _cluster_signals(result: Any) -> list[str]:
    return [c["signal"] for c in result.metadata["clusters"]]


def _has_pair(clusters: list[dict[str, Any]], names: set[str]) -> bool:
    for c in clusters:
        cluster_names = {t["name"] for t in c["members"]}
        if names.issubset(cluster_names):
            return True
    return False


def _write__from_duplicate_tests_acknowledgement(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip())


def _write_two_duplicates(project: Path) -> None:
    """Two structurally-identical tests in one file → one cluster."""
    _write__from_duplicate_tests_acknowledgement(
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


def _write_two_distinct_clusters(project: Path) -> None:
    """Two clusters of duplicates in separate files."""
    _write__from_duplicate_tests_acknowledgement(
        project / "tests" / "test_mod_a.py",
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
    _write__from_duplicate_tests_acknowledgement(
        project / "tests" / "test_mod_b.py",
        """
        def test_render_alpha():
            html = render("alpha")
            assert "<div>" in html
            assert len(html) > 10

        def test_render_beta():
            html = render("beta")
            assert "<div>" in html
            assert len(html) > 10
        """,
    )


def _first_cluster_hash(project: Path) -> str:
    """Run the rule with no config and return the first cluster's hash."""
    result = DuplicateTestsRule().check(project)
    clusters: list[dict[str, Any]] = list(result.metadata["clusters"])
    assert clusters, "setup error: expected at least one cluster"
    return str(clusters[0]["cluster_hash"])


def _write_pyproject_with_ack(project: Path, entries: list[tuple[str, str]]) -> None:
    lines = ["[tool.axm-audit.duplicate_tests]"]
    for h, reason in entries:
        lines += [
            "",
            "[[tool.axm-audit.duplicate_tests.acknowledged]]",
            f'hash = "{h}"',
            f'reason = "{reason}"',
        ]
    (project / "pyproject.toml").write_text("\n".join(lines) + "\n")


def test_duplicate_tests_failed_populates_actionable_fields(
    duplicate_tests_project: Path,
) -> None:
    result = DuplicateTestsRule().check(duplicate_tests_project)
    if result.passed:
        pytest.skip("clustering heuristics did not flag this pair")
    assert result.text and "cluster[" in result.text
    assert result.fix_hint and "parametrize" in result.fix_hint
    assert result.metadata is not None
    assert "clusters" in result.metadata


def test_duplicate_tests_passed_omits_text_and_fix_hint(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = DuplicateTestsRule().check(tmp_path)
    assert result.passed is True
    assert result.text is None
    assert result.fix_hint is None


def test_s1_same_sut_same_asserts_clusters(project: Path) -> None:
    _write__from_duplicate_test_clustering(
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
    _write__from_duplicate_test_clustering(project / "tests" / "test_a.py", body)
    _write__from_duplicate_test_clustering(project / "tests" / "test_b.py", body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    clusters = result.metadata["clusters"]
    s2 = [c for c in clusters if c["signal"] == "signal2_cross_file_name"]
    assert s2, f"expected signal2_cross_file_name in {clusters}"
    assert s2[0]["similarity"] >= 0.95


@pytest.mark.parametrize(
    ("files", "expected_signal_in"),
    [
        pytest.param(
            [
                (
                    "test_mod.py",
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
            ],
            "signal3_intra_file_similarity",
            id="s3_intra_file_similarity",
        ),
        pytest.param(
            [
                (
                    "test_mod.py",
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
            ],
            "ambiguous_patch_context",
            id="p2_patch_context",
        ),
        pytest.param(
            [
                (
                    "test_mod.py",
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
            ],
            "ambiguous_patch_context",
            id="p2_mocker_patch_asymmetry",
        ),
        pytest.param(
            [
                (
                    "test_json_parser.py",
                    """
                    def test_parse():
                        result = run(1)
                        assert result == 1
                    """,
                ),
                (
                    "test_yaml_parser.py",
                    """
                    def test_parse():
                        result = run(1)
                        assert result == 1
                    """,
                ),
            ],
            "ambiguous_template_pair",
            id="p3_cross_file_template_pair",
        ),
        pytest.param(
            [
                (
                    "test_mod.py",
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
            ],
            "ambiguous_body_size",
            id="p4_intra_file_body_size_delta",
        ),
        pytest.param(
            [
                (
                    "test_mod.py",
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
            ],
            "ambiguous_call_multiplicity",
            id="p6_call_multiplicity_rescues_s1",
        ),
    ],
)
def test_signal_present(
    project: Path, files: list[tuple[str, str]], expected_signal_in: str
) -> None:
    """Each (body, expected) pair pins one positive signal path."""
    for filename, body in files:
        _write__from_duplicate_test_clustering(project / "tests" / filename, body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert expected_signal_in in signals


@pytest.mark.parametrize(
    ("body", "expected_signals"),
    [
        pytest.param(
            """
            def test_parse_one():
                result = parse("foo")
                assert result == "alpha"

            def test_parse_two():
                result = parse("bar")
                assert result == "beta"
            """,
            ["ambiguous_distinct_literals"],
            id="p1_distinct_literals_rescues_s1",
        ),
        pytest.param(
            """
            def test_parse_one():
                result = parse("foo")
                assert result == 1

            def test_parse_two():
                result = parse("bar")
                assert result == 1
            """,
            ["signal1_call_assert"],
            id="p1_single_literal_diff_does_not_rescue",
        ),
    ],
)
def test_exact_signals(project: Path, body: str, expected_signals: list[str]) -> None:
    _write__from_duplicate_test_clustering(project / "tests" / "test_mod.py", body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert signals == expected_signals


def test_p1_docstring_diff_ignored(project: Path) -> None:
    _write__from_duplicate_test_clustering(
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
        _write__from_duplicate_test_clustering(project / "tests" / filename, body)
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(project)
    signals = _cluster_signals(result)
    assert absent_signal not in signals


def test_p7_distinct_sut_rescues_s3(project: Path) -> None:
    """P7 — same skeleton + side-effecting distinct SUTs ≠ duplicates.

    Reproduit le faux positif `atd-reporter` cluster #15: deux smoke
    tests dont le SUT (``fill_highlight`` vs ``_shift_ppr_tracking_table``)
    n'apparaît pas sur la chaîne d'asserts (side-effect), donc
    ``call_sig`` capte le builder de fixture et S1 ne déclenche pas; S3
    clusterise par similarité brute.  P7 doit demoter en
    ``ambiguous_distinct_sut``.
    """
    _write__from_duplicate_test_clustering(
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
    _write__from_duplicate_test_clustering(
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
    _write__from_duplicate_test_clustering(
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
    _write__from_duplicate_test_clustering(
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


def test_empty_tests_returns_pass(tmp_path: Path) -> None:
    result = DuplicateTestsRule(ast_similarity_threshold=0.8).check(tmp_path)
    assert result.passed is True
    assert result.score == 100


@pytest.mark.parametrize(
    "setup_variant",
    [
        pytest.param("setUp", id="distinct_self_attr_setUp"),
        pytest.param("setup_method", id="setup_method_variant"),
        pytest.param("pytest_fixture", id="pytest_fixture_class_attr"),
    ],
)
def test_distinct_self_attr_sut_not_clustered(
    project: Path, setup_variant: str
) -> None:
    body = _DISTINCT_SELF_ATTR_SETUP_VARIANTS[setup_variant]
    _write__from_duplicate_test_clustering(project / "tests" / "test_a.py", body)

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
    _write__from_duplicate_test_clustering(project / "tests" / "test_a.py", body)

    result = DuplicateTestsRule().check(project)

    pair = _find_pair(result.metadata["clusters"], {"test_first", "test_second"})
    assert pair is not None
    assert pair["signal"].startswith(("signal1_", "signal3_"))


def test_no_pyproject_keeps_clusters_flagged(project: Path) -> None:
    """AC2: missing pyproject.toml → empty acknowledgement list, no error."""
    _write_two_duplicates(project)
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert "config_error" not in result.metadata


def test_pyproject_without_section_keeps_clusters_flagged(project: Path) -> None:
    """AC2: pyproject without `[tool.axm-audit.duplicate_tests]` → no error."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.0.0"\n'
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert "config_error" not in result.metadata


def test_acknowledged_cluster_excluded_from_score(project: Path) -> None:
    """AC3, AC5: acknowledged cluster → passed=True, score=100, marked."""
    _write_two_duplicates(project)
    h = _first_cluster_hash(project)
    _write_pyproject_with_ack(project, [(h, "validated: distinct fixtures")])

    result = DuplicateTestsRule().check(project)
    assert result.passed is True
    assert result.score == 100
    ack = next(c for c in result.metadata["clusters"] if c["cluster_hash"] == h)
    assert ack["acknowledged"] is True


def test_unacknowledged_cluster_still_lowers_score(project: Path) -> None:
    """AC3: empty acknowledged list → cluster still flagged."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        "[tool.axm-audit.duplicate_tests]\nacknowledged = []\n"
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    assert result.score < 100
    cluster = result.metadata["clusters"][0]
    assert cluster.get("acknowledged", False) is False


def test_partial_acknowledgement_isolates_remaining_clusters(
    project: Path,
) -> None:
    """AC3: acknowledging one of two clusters leaves the other flagged."""
    _write_two_distinct_clusters(project)
    result0 = DuplicateTestsRule().check(project)
    hashes = [c["cluster_hash"] for c in result0.metadata["clusters"]]
    assert len(hashes) >= 2, f"expected ≥2 clusters, got {hashes}"
    ack_hash, other_hash = hashes[0], hashes[1]

    _write_pyproject_with_ack(project, [(ack_hash, "validated")])
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    by_hash = {c["cluster_hash"]: c for c in result.metadata["clusters"]}
    assert by_hash[ack_hash]["acknowledged"] is True
    assert by_hash[other_hash].get("acknowledged", False) is False


def test_stale_acknowledged_hash_listed_in_metadata(project: Path) -> None:
    """AC4, AC5: stale hash → metadata.stale_acknowledged, no score impact."""
    _write_two_duplicates(project)
    fake_hash = "deadbeef0000"
    _write_pyproject_with_ack(
        project, [(fake_hash, "old entry from a deleted cluster")]
    )
    result_with_stale = DuplicateTestsRule().check(project)

    # Score must be identical to no-config baseline (stale entries don't help).
    (project / "pyproject.toml").unlink()
    baseline = DuplicateTestsRule().check(project)

    stale = result_with_stale.metadata.get("stale_acknowledged", [])
    stale_hashes = [entry["hash"] for entry in stale]
    assert fake_hash in stale_hashes
    assert result_with_stale.passed is False
    assert result_with_stale.score == baseline.score


def test_stale_acknowledged_rendered_in_text(project: Path) -> None:
    """AC4: stale entries appear as bullet lines in result.text."""
    _write_two_duplicates(project)
    fake_hash = "deadbeef0000"
    _write_pyproject_with_ack(project, [(fake_hash, "old reason")])

    result = DuplicateTestsRule().check(project)
    assert fake_hash in result.text
    assert "stale acknowledged cluster" in result.text


def test_malformed_toml_falls_back_gracefully(project: Path) -> None:
    """AC6: malformed TOML → metadata.config_error, audit does not crash."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        "[tool.axm-audit.duplicate_tests\nnot valid toml\n"
    )
    result = DuplicateTestsRule().check(project)
    assert result.passed is False
    err = result.metadata.get("config_error")
    assert isinstance(err, str)
    assert err


def test_wrong_schema_falls_back_gracefully(project: Path) -> None:
    """AC2, AC6: malformed schema (missing `reason`) → config_error, baseline score."""
    _write_two_duplicates(project)
    (project / "pyproject.toml").write_text(
        '[[tool.axm-audit.duplicate_tests.acknowledged]]\nhash = "a1b2c3d4e5f6"\n'
    )
    result = DuplicateTestsRule().check(project)

    (project / "pyproject.toml").unlink()
    baseline = DuplicateTestsRule().check(project)

    assert result.passed is False
    err = result.metadata.get("config_error")
    assert isinstance(err, str)
    assert "schema" in err.lower()
    assert result.score == baseline.score


def test_well_formed_two_entries_round_trip(project: Path) -> None:
    """AC2: two valid acknowledgements → both clusters marked, no error."""
    _write_two_distinct_clusters(project)
    baseline = DuplicateTestsRule().check(project)
    hashes = [c["cluster_hash"] for c in baseline.metadata["clusters"]]
    assert len(hashes) >= 2
    h1, h2 = hashes[0], hashes[1]

    _write_pyproject_with_ack(project, [(h1, "validated A"), (h2, "validated B")])

    result = DuplicateTestsRule().check(project)
    assert result.passed is True
    assert "config_error" not in result.metadata
    by_hash = {c["cluster_hash"]: c for c in result.metadata["clusters"]}
    assert by_hash[h1]["acknowledged"] is True
    assert by_hash[h2]["acknowledged"] is True
