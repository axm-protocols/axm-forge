"""Unit tests for AntiMirrorRule registry presence and K=1 suppression."""

from __future__ import annotations

from pathlib import Path


def test_anti_mirror_rule_registered_or_absent(registry: dict[str, list[type]]) -> None:
    """AntiMirrorRule, if registered, lives in the practices bucket."""
    bucket = registry.get("practices", [])
    names = {cls.__name__ for cls in bucket}
    # Tolerate either presence or absence — the rule may not auto-register.
    if "AntiMirrorRule" in names:
        from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

        assert any(cls is AntiMirrorRule for cls in bucket)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _mk_pkg(tmp_path: Path, name: str = "pkg") -> Path:
    pkg_dir = tmp_path / "src" / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("")
    return pkg_dir


def test_suppressed_when_canonical_k1_matches_stem(tmp_path: Path) -> None:
    """AC1: stem matches K=1 canonical name → suppress anti-mirror violation."""
    from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    _write(
        tmp_path / "tests" / "integration" / "test_foo.py",
        "from pkg.foo import foo\n\ndef test_foo():\n    assert foo() == 1\n",
    )

    result = AntiMirrorRule().check(tmp_path)

    assert result.passed is True
    assert result.details is not None
    assert result.details["anti_mirror"] == []


def test_not_suppressed_when_two_tuples(tmp_path: Path) -> None:
    """AC2: stem mirrors src AND >=2 distinct tuples → violation still fires."""
    from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

    pkg_dir = _mk_pkg(tmp_path)
    _write(
        pkg_dir / "foo.py",
        "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n",
    )
    _write(
        tmp_path / "tests" / "integration" / "test_foo.py",
        (
            "from pkg.foo import foo, bar\n\n"
            "def test_foo():\n    assert foo() == 1\n\n"
            "def test_bar():\n    assert bar() == 2\n"
        ),
    )

    result = AntiMirrorRule().check(tmp_path)

    assert result.passed is False
    assert result.details is not None
    assert "tests/integration/test_foo.py" in result.details["anti_mirror"]


def test_not_suppressed_when_stem_differs_from_canonical(tmp_path: Path) -> None:
    """AC3: stem mirrors a src module but tests cover a different symbol → fire."""
    from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    _write(pkg_dir / "bar.py", "def bar():\n    return 2\n")
    _write(
        tmp_path / "tests" / "integration" / "test_foo.py",
        "from pkg.bar import bar\n\ndef test_bar():\n    assert bar() == 2\n",
    )

    result = AntiMirrorRule().check(tmp_path)

    assert result.passed is False
    assert result.details is not None
    assert "tests/integration/test_foo.py" in result.details["anti_mirror"]


def test_compute_canonical_name_none_keeps_violation(tmp_path: Path) -> None:
    """AC1: compute_canonical_name returns None (no tests) → violation still fires."""
    from axm_audit.core.rules.practices.anti_mirror import AntiMirrorRule

    pkg_dir = _mk_pkg(tmp_path)
    _write(pkg_dir / "foo.py", "def foo():\n    return 1\n")
    _write(
        tmp_path / "tests" / "integration" / "test_foo.py",
        "# no test functions\n",
    )

    result = AntiMirrorRule().check(tmp_path)

    assert result.passed is False
    assert result.details is not None
    assert "tests/integration/test_foo.py" in result.details["anti_mirror"]
