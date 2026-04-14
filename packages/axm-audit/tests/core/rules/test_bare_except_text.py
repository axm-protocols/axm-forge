from __future__ import annotations

from pathlib import Path

import pytest

from axm_audit.core.rules.practices import BareExceptRule

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


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


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


def test_bare_except_text_short_paths(tmp_path: Path, rule: BareExceptRule) -> None:
    """Bare except in pkg/sub/module.py -> bullet shows sub/module.py:N."""
    project = _make_project(
        tmp_path,
        {
            "sub/module.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is not None
    assert "sub/module.py:" in result.text
    # Must NOT contain the full path with package prefix
    assert "pkg/sub/module.py" not in result.text


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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_bare_except_text_top_level_file(tmp_path: Path, rule: BareExceptRule) -> None:
    """Bare except in pkg/cli.py (1 part after package) -> cli.py:N."""
    project = _make_project(
        tmp_path,
        {
            "cli.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is not None
    assert "cli.py:" in result.text
    # Should NOT include pkg/ prefix
    assert "pkg/cli.py" not in result.text


def test_bare_except_text_deeply_nested(tmp_path: Path, rule: BareExceptRule) -> None:
    """Bare except in pkg/a/b/c/deep.py -> c/deep.py:N (last 2 parts)."""
    project = _make_project(
        tmp_path,
        {
            "a/b/c/deep.py": "try:\n    pass\nexcept:\n    pass\n",
        },
    )
    result = rule.check(project)
    assert result.text is not None
    assert "c/deep.py:" in result.text
    # Must not show full nested path
    assert "a/b/c/deep.py" not in result.text


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
