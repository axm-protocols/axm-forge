"""Split from ``test_practices.py``."""

from pathlib import Path

import pytest

from axm_audit.core.rules.practices.bare_except import BareExceptRule


class TestBareExceptRuleIntegration:
    """Tests for BareExceptRule (real I/O)."""

    def test_typed_except_passes(self, tmp_path: Path) -> None:
        """Typed except clauses should pass."""
        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "good.py").write_text("""
try:
    x = 1 / 0
except ZeroDivisionError:
    pass
except (ValueError, TypeError) as e:
    print(e)
""")

        rule = BareExceptRule()
        result = rule.check(tmp_path)
        assert result.passed is True

    def test_bare_except_fails(self, tmp_path: Path) -> None:
        """Bare except: should fail."""
        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text("""
try:
    risky_operation()
except:
    pass  # Bare except!
""")

        rule = BareExceptRule()
        result = rule.check(tmp_path)
        assert result.passed is False
        assert result.details is not None
        assert result.details["bare_except_count"] > 0

    def test_find_bare_excepts_helper(self, tmp_path: Path) -> None:
        """Tests that _find_bare_excepts correctly extracts locations."""
        import ast

        from axm_audit.core.rules.practices.bare_except import BareExceptRule

        src_path = tmp_path / "src"
        src_path.mkdir()

        file_path = src_path / "bad.py"
        file_path.write_text("""
try:
    risky_operation()
except:
    pass  # Bare except!
""")

        tree = ast.parse(file_path.read_text())
        rule = BareExceptRule()
        bare_excepts: list[dict[str, str | int]] = []
        rule._find_bare_excepts(tree, file_path, src_path, bare_excepts)

        assert len(bare_excepts) == 1
        assert bare_excepts[0]["file"] == "bad.py"
        assert bare_excepts[0]["line"] == 4


BULLET = "     \u2022 "


@pytest.fixture()
def rule() -> BareExceptRule:
    return BareExceptRule()


def _make_project(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a minimal project layout under tmp_path with src/pkg/."""
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    for rel, content in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


def test_bare_except_text_none_when_passed(
    tmp_path: Path, rule: BareExceptRule
) -> None:
    """Project with no bare excepts -> result.text is None."""
    project = _make_project(
        tmp_path,
        {
            "clean.py": "try:\n    pass\nexcept ValueError:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is None


def test_bare_except_text_bullets_on_failure(
    tmp_path: Path, rule: BareExceptRule
) -> None:
    """Project with 2+ bare excepts in different modules -> bullets."""
    project = _make_project(
        tmp_path,
        {
            "sub/alpha.py": "try:\n    pass\nexcept:\n    pass\n",
            "sub/beta.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 2
    for line in lines:
        assert line.startswith(BULLET)


@pytest.mark.parametrize(
    ("rel_path", "expected_fragment", "excluded_fragment"),
    [
        pytest.param(
            "sub/module.py",
            "sub/module.py:",
            "pkg/sub/module.py",
            id="short_paths",
        ),
        pytest.param(
            "cli.py",
            "cli.py:",
            "pkg/cli.py",
            id="top_level_file",
        ),
        pytest.param(
            "a/b/c/deep.py",
            "c/deep.py:",
            "a/b/c/deep.py",
            id="deeply_nested",
        ),
    ],
)
def test_bare_except_text_path_shortening(
    tmp_path: Path,
    rule: BareExceptRule,
    rel_path: str,
    expected_fragment: str,
    excluded_fragment: str,
) -> None:
    """Bare excepts show shortened paths in text bullets."""
    project = _make_project(
        tmp_path,
        {rel_path: "try:\n    pass\nexcept:\n    pass\n"},
    )
    result = rule.check(project)
    assert result.text is not None
    assert expected_fragment in result.text
    assert excluded_fragment not in result.text


def test_bare_except_text_single_location(tmp_path: Path, rule: BareExceptRule) -> None:
    """Project with exactly 1 bare except -> single bullet line."""
    project = _make_project(
        tmp_path,
        {
            "dir/file.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is not None
    lines = result.text.split("\n")
    assert len(lines) == 1
    assert lines[0].startswith(BULLET)
    assert "dir/file.py:" in lines[0]


def test_bare_except_details_unchanged(tmp_path: Path, rule: BareExceptRule) -> None:
    """details dict keeps full relative paths and bare_except_count."""
    project = _make_project(
        tmp_path,
        {
            "sub/alpha.py": "try:\n    pass\nexcept:\n    pass\n",
            "sub/beta.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.details is not None
    assert result.details["bare_except_count"] == 2
    locations = result.details["locations"]
    assert len(locations) == 2
    # Locations must contain full relative paths (not shortened)
    files = sorted(loc["file"] for loc in locations)
    assert any("pkg/sub/alpha.py" in f for f in files)
    assert any("pkg/sub/beta.py" in f for f in files)
