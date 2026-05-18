"""Split from ``test_practices.py``."""

from pathlib import Path


def test_invalid_toml_does_not_crash(tmp_path: Path) -> None:
    """AC9: malformed pyproject.toml returns CheckResult, no exception."""
    from axm_audit.core.rules.practices.mirror import MirrorRule
    from axm_audit.models.results import CheckResult

    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "foo.py").write_text("x = 1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text("this is = = not valid toml [[[\n")

    result = MirrorRule().check(tmp_path)
    assert isinstance(result, CheckResult)
    assert result.passed is False
