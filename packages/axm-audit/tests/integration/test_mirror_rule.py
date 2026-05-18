from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices.mirror import MirrorRule

pytestmark = pytest.mark.integration


def _write(p: Path, text: str = "") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_mirror_layout_partitions_missing_and_exempt(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "pkg" / "a.py", "x = 1\n")
    _write(tmp_path / "src" / "pkg" / "sub" / "b.py", "y = 2\n")
    _write(tmp_path / "tests" / "unit" / "test_a.py", "")
    _write(
        tmp_path / "pyproject.toml",
        '[tool.axm-audit.mirror]\nexempt_paths = ["sub/*"]\n',
    )

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert "b.py" in result.details["exempt"]
    assert "b.py" not in result.details["missing"]
    assert "a.py" not in result.details["missing"]


def test_flat_layout_falls_back_to_basename_match(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "pkg" / "a.py", "x = 1\n")
    _write(tmp_path / "tests" / "test_a.py", "")

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert "a.py" not in result.details["missing"]
    assert result.details["exempt"] == []


def test_empty_src_returns_empty_lists(tmp_path: Path) -> None:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "tests").mkdir()

    result = MirrorRule().check(tmp_path)
    assert result.details is not None

    assert result.details["missing"] == []
    assert result.details["exempt"] == []


def _write__from_practices(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_pass_all_modules_tested(tmp_path: Path) -> None:
    """All source modules with matching test files should pass."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def hello(): pass\n")
    (pkg / "b.py").write_text("def world(): pass\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("def test_a(): pass\n")
    (tests / "test_b.py").write_text("def test_b(): pass\n")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True
    assert result.fix_hint is None


def test_fail_missing_tests(tmp_path: Path) -> None:
    """Missing test file should fail with details listing the module."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("def hello(): pass\n")
    (pkg / "b.py").write_text("def world(): pass\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("def test_a(): pass\n")
    # No test_b.py!

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is False
    assert result.details is not None
    assert "b.py" in result.details["missing"]
    assert result.fix_hint is not None
    assert "test_b.py" in result.fix_hint


def test_exempt_init_main_and_version(tmp_path: Path) -> None:
    """__init__/__main__/_version are exempt from test requirement."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text("print('hi')\n")
    (pkg / "_version.py").write_text("__version__ = '0.1'\n")
    (pkg / "a.py").write_text("def hello(): pass\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("def test_a(): pass\n")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert result.details["missing"] == []


def test_nested_test_dirs(tmp_path: Path) -> None:
    """Test files in nested directories (tests/core/) should match."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "foo.py").write_text("def foo(): pass\n")

    tests = tmp_path / "tests" / "core"
    tests.mkdir(parents=True)
    (tests / "test_foo.py").write_text("def test_foo(): pass\n")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True


def test_empty_src_only_init(tmp_path: Path) -> None:
    """Package with only __init__.py should pass (all exempt)."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True


@pytest.mark.parametrize(
    ("src_module", "test_filename"),
    [
        pytest.param("_facade.py", "test_facade.py", id="single_underscore_stripped"),
        pytest.param("_facade.py", "test__facade.py", id="single_underscore_exact"),
        pytest.param(
            "__internal.py", "test_internal.py", id="double_underscore_stripped"
        ),
        pytest.param("___triple.py", "test_triple.py", id="triple_underscore_stripped"),
    ],
)
def test_underscore_stripped_module_matches(
    tmp_path: Path, src_module: str, test_filename: str
) -> None:
    """Private modules with leading underscores match stripped test names."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / src_module).write_text("x = 1\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / test_filename).write_text("def test_x(): pass\n")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True
    assert result.details is None or src_module not in result.details.get("missing", [])


def test_public_module_unchanged(tmp_path: Path) -> None:
    """Public module base.py should still match test_base.py unchanged."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "base.py").write_text("class Base: pass\n")

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_base.py").write_text("def test_base(): pass\n")

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is True


@pytest.mark.parametrize(
    ("src_module", "test_dirs", "test_files", "expected_missing"),
    [
        pytest.param(
            "_facade.py",
            ("tests",),
            (),
            "_facade.py",
            id="private_module_no_test",
        ),
        pytest.param(
            "foo.py",
            ("tests/unit", "tests/integration"),
            (("tests/integration/test_foo.py", "def test_foo(): pass\n"),),
            "foo.py",
            id="unit_dir_present_only_unit_counts",
        ),
        pytest.param(
            "foo.py",
            ("tests/e2e",),
            (("tests/e2e/test_foo.py", "def test_foo(): pass\n"),),
            "foo.py",
            id="flat_layout_excludes_integration_and_e2e",
        ),
    ],
)
def test_module_missing_test_appears_in_missing(
    tmp_path: Path,
    src_module: str,
    test_dirs: tuple[str, ...],
    test_files: tuple[tuple[str, str], ...],
    expected_missing: str,
) -> None:
    """Modules without a unit-level test are reported in details['missing']."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / src_module).write_text("class X: pass\n")

    for rel_dir in test_dirs:
        (tmp_path / rel_dir).mkdir(parents=True, exist_ok=True)
    for rel_file, content in test_files:
        (tmp_path / rel_file).write_text(content)

    rule = MirrorRule()
    result = rule.check(tmp_path)
    assert result.passed is False
    assert result.details is not None
    assert expected_missing in result.details["missing"]


def test_exempt_paths_skips_listed_modules(tmp_path: Path) -> None:
    """AC1, AC2: exempt_paths glob skips matching modules from missing."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    (pkg / "commands").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "commands" / "__init__.py").write_text("")
    (pkg / "commands" / "data.py").write_text("def x(): pass\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["commands/*.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert "data.py" not in result.details["missing"]
    assert "data.py" in result.details["exempt"]


def test_no_config_section_backwards_compatible(tmp_path: Path) -> None:
    """AC3: missing config section preserves legacy behavior."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "foo.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'pkg'\n")

    result = MirrorRule().check(tmp_path)
    assert result.passed is False
    assert result.details is not None
    assert "foo.py" in result.details["missing"]
    assert result.details["exempt"] == []


def test_double_star_glob_matches_nested(tmp_path: Path) -> None:
    """AC4, AC8: ** glob matches nested paths."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sub" / "__init__.py").write_text("")
    (pkg / "sub" / "_facade.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["**/_facade.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert "_facade.py" not in result.details["missing"]
    assert "_facade.py" in result.details["exempt"]


def test_question_mark_glob(tmp_path: Path) -> None:
    """AC4: ? glob matches a single character."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "v1.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["v?.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert "v1.py" not in result.details["missing"]
    assert "v1.py" in result.details["exempt"]


def test_single_star_does_not_cross_slash(tmp_path: Path) -> None:
    """AC8: single * must not match across path separators."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sub" / "__init__.py").write_text("")
    (pkg / "sub" / "foo.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["*.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.details is not None
    assert "foo.py" in result.details["missing"]
    assert "foo.py" not in result.details["exempt"]


def test_exempt_module_with_test_still_allowed(tmp_path: Path) -> None:
    """AC5: exempt module that has a test is still allowed and listed in exempt."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "data.py").write_text("x = 1\n")
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "test_data.py").write_text("def test_data(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["data.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is True
    assert result.details is not None
    assert result.details["missing"] == []
    assert "data.py" in result.details["exempt"]


def test_details_exempt_lists_exempted_modules(tmp_path: Path) -> None:
    """AC6: details['exempt'] lists exempted module basenames."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "b.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["a.py", "b.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.details is not None
    assert set(result.details["exempt"]) == {"a.py", "b.py"}


def test_all_missing_exempted_passes(tmp_path: Path) -> None:
    """AC7: when all missing modules are exempt, pass with score=100."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "b.py").write_text("x = 1\n")
    (pkg / "c.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["a.py", "b.py", "c.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is True
    assert result.score == 100


def test_invalid_exempt_paths_type_reported(tmp_path: Path) -> None:
    """AC9: invalid exempt_paths type fails with a fix_hint, no exception."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "foo.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = "not-a-list"\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.passed is False
    assert result.fix_hint is not None
    assert (
        "exempt_paths" in result.fix_hint.lower()
        or "list" in result.fix_hint.lower()
        or "malform" in result.fix_hint.lower()
    )


def test_exemption_does_not_affect_reverse(tmp_path: Path) -> None:
    """AC10: forward exemption never leaks into reverse orphan check."""
    from axm_audit.core.rules.practices.mirror import MirrorRule

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "real.py").write_text("x = 1\n")
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    (unit / "test_real.py").write_text("def test_real(): pass\n")
    (unit / "test_ghost.py").write_text("def test_ghost(): pass\n")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.axm-audit.mirror]\nexempt_paths = ["ghost.py", "real.py"]\n'
    )

    result = MirrorRule().check(tmp_path)
    assert result.details is not None
    assert "tests/unit/test_ghost.py" in result.details["orphan"]


class TestMirrorRuleOrphanIntegration:
    """Reverse mirror check — orphan unit tests (AC1-AC9)."""

    def test_orphan_test_no_matching_source(self, tmp_path: Path) -> None:
        """AC1: a tests/unit/test_*.py with no matching src module is orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        orphan = result.details["orphan"]
        assert any("test_ghost.py" in o for o in orphan)
        assert "foo.py" not in result.details["missing"]

    def test_orphan_test_misplaced_arborescence(self, tmp_path: Path) -> None:
        """AC2: a test at tests/unit/ root that should mirror a nested src is orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "sub" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "sub" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is False
        assert result.details is not None
        orphan = result.details["orphan"]
        assert any("test_foo.py" in o for o in orphan)
        assert "foo.py" in result.details["missing"]

    def test_orphan_correct_arborescence_passes(self, tmp_path: Path) -> None:
        """AC2: a properly-nested test mirroring its src is not orphan."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "sub" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "sub" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "sub" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_orphan_details_key_distinct_from_missing(self, tmp_path: Path) -> None:
        """AC3: details['orphan'] and details['missing'] are disjoint."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "alpha.py", "x = 1\n")
        _write__from_practices(tmp_path / "src" / "pkg" / "beta.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_alpha.py", "")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_orphanxyz.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.details is not None
        missing = result.details["missing"]
        orphan = result.details["orphan"]
        assert missing
        assert orphan
        orphan_basenames = {Path(o).name for o in orphan}
        assert set(missing).isdisjoint(orphan_basenames)

    def test_orphan_fix_hint_suggests_close_match(self, tmp_path: Path) -> None:
        """AC4: fix_hint proposes the closest source basename for typos."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "helpers.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_helpres.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.fix_hint is not None
        assert "rename" in result.fix_hint.lower()
        assert "test_helpers.py" in result.fix_hint

    def test_orphan_fix_hint_no_close_match(self, tmp_path: Path) -> None:
        """AC4: fix_hint mentions orphan + suggests delete/rename when no match."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_zzzzqqqq.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.fix_hint is not None
        assert "test_zzzzqqqq.py" in result.fix_hint
        hint_lower = result.fix_hint.lower()
        assert "delete" in hint_lower or "rename" in hint_lower

    def test_orphan_text_line_present(self, tmp_path: Path) -> None:
        """AC5: result.text contains a '• orphan:' bullet line."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.text is not None
        assert any(line.startswith("• orphan:") for line in result.text.splitlines())

    @pytest.mark.parametrize(
        ("extra_src", "expected_score"),
        [
            pytest.param(["bar.py"], 70, id="one_missing_one_orphan"),
            pytest.param([], 85, id="zero_missing_one_orphan"),
        ],
    )
    def test_score_missing_and_orphan(
        self, tmp_path: Path, extra_src: list[str], expected_score: int
    ) -> None:
        """AC6: score reflects missing + orphan penalties."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        for name in extra_src:
            _write__from_practices(tmp_path / "src" / "pkg" / name, "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_foo.py", "")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_ghost.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.score == expected_score

    @pytest.mark.parametrize(
        "extra_files",
        [
            pytest.param(
                ["tests/integration/test_anything.py"],
                id="integration_test_not_flagged",
            ),
            pytest.param(
                ["tests/e2e/test_anything.py"],
                id="e2e_test_not_flagged",
            ),
            pytest.param(
                ["tests/unit/__init__.py", "tests/unit/conftest.py"],
                id="init_and_conftest_excluded",
            ),
        ],
    )
    def test_extra_test_files_not_flagged_as_orphan(
        self, tmp_path: Path, extra_files: list[str]
    ) -> None:
        """AC7/AC8: integration/e2e tests and __init__/conftest are not orphans."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "unit" / "test_foo.py", "")
        for rel in extra_files:
            _write__from_practices(tmp_path / rel, "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_no_unit_dir_no_orphan_check(self, tmp_path: Path) -> None:
        """AC9: legacy flat layout (no tests/unit/) skips reverse check."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        _write__from_practices(tmp_path / "tests" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []

    def test_empty_unit_dir_no_orphan(self, tmp_path: Path) -> None:
        """AC9: empty tests/unit/ produces no orphans."""
        from axm_audit.core.rules.practices.mirror import MirrorRule

        _write__from_practices(tmp_path / "src" / "pkg" / "__init__.py")
        _write__from_practices(tmp_path / "src" / "pkg" / "foo.py", "x = 1\n")
        (tmp_path / "tests" / "unit").mkdir(parents=True)
        _write__from_practices(tmp_path / "tests" / "test_foo.py", "")

        result = MirrorRule().check(tmp_path)

        assert result.passed is True
        assert result.details is not None
        assert result.details["orphan"] == []


class TestMirrorRule:
    """Tests for MirrorRule.check text= rendering."""

    @pytest.fixture()
    def rule(self) -> MirrorRule:
        return MirrorRule()

    @staticmethod
    def _make_project(
        tmp_path: Path,
        src_modules: list[str],
        test_files: list[str],
    ) -> Path:
        """Create a minimal project with src/<pkg>/ modules and tests/ files."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        for m in src_modules:
            (pkg / m).touch()
        tests = tmp_path / "tests"
        tests.mkdir()
        for t in test_files:
            (tests / t).touch()
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "mypkg"\n')
        return tmp_path

    # --- Unit tests ---

    def test_fail_missing_tests_has_text(
        self, rule: MirrorRule, tmp_path: Path
    ) -> None:
        """Failed result text starts with bullet and contains missing module."""
        project = self._make_project(
            tmp_path,
            src_modules=["a.py", "b.py"],
            test_files=["test_a.py"],
        )
        result = rule.check(project)
        assert result.text is not None
        assert result.text.startswith("\u2022 untested:")
        assert "b.py" in result.text

    def test_text_truncation_above_five(self, rule: MirrorRule, tmp_path: Path) -> None:
        """Text truncates at 5 filenames with (+N more) suffix."""
        project = self._make_project(
            tmp_path,
            src_modules=[f"mod{i}.py" for i in range(7)],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "(+2 more)" in result.text
        # Exactly 5 filenames listed before the suffix
        text_before_suffix = result.text.split("(+")[0]
        assert text_before_suffix.count(".py") == 5

    def test_passed_no_text(self, rule: MirrorRule, tmp_path: Path) -> None:
        """Passed result (all modules tested) has text=None."""
        project = self._make_project(
            tmp_path,
            src_modules=["a.py", "b.py"],
            test_files=["test_a.py", "test_b.py"],
        )
        result = rule.check(project)
        assert result.text is None

    # --- Edge cases ---

    def test_exactly_five_missing_no_suffix(
        self, rule: MirrorRule, tmp_path: Path
    ) -> None:
        """Exactly 5 missing modules lists all without (+N more)."""
        project = self._make_project(
            tmp_path,
            src_modules=[f"mod{i}.py" for i in range(5)],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "(+" not in result.text
        assert result.text.count(".py") == 5

    def test_single_missing_no_truncation(
        self, rule: MirrorRule, tmp_path: Path
    ) -> None:
        """Single missing module: no truncation, just the filename."""
        project = self._make_project(
            tmp_path,
            src_modules=["utils.py"],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "\u2022 untested: utils.py" in result.text
        assert "(+" not in result.text

    def test_private_module_listed(self, rule: MirrorRule, tmp_path: Path) -> None:
        """Private module _facade.py appears in text."""
        project = self._make_project(
            tmp_path,
            src_modules=["_facade.py"],
            test_files=[],
        )
        result = rule.check(project)
        assert result.text is not None
        assert "_facade.py" in result.text
