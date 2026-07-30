"""Split from ``test_shared_helpers_io.py``."""

from pathlib import Path

from axm_audit.core.rules.test_quality._shared import iter_test_files


def test_iter_test_files_yields_tests_recursively(tmp_path: Path) -> None:
    unit = tmp_path / "tests" / "unit"
    integ = tmp_path / "tests" / "integration"
    unit.mkdir(parents=True)
    integ.mkdir(parents=True)
    (unit / "test_a.py").write_text("")
    (integ / "test_b.py").write_text("")

    results = list(iter_test_files(tmp_path))
    paths = [r[0] if isinstance(r, tuple) else r for r in results]
    names = [Path(p).name for p in paths]
    assert "test_a.py" in names
    assert "test_b.py" in names
    assert paths == sorted(paths)


def test_iter_test_files_skips_fixtures(tmp_path: Path) -> None:
    """`tests/fixtures/**/test_*.py` is corpus data, not real tests."""
    unit = tmp_path / "tests" / "unit"
    corpus = tmp_path / "tests" / "fixtures" / "corpus" / "input" / "tests" / "unit"
    unit.mkdir(parents=True)
    corpus.mkdir(parents=True)
    (unit / "test_real.py").write_text("")
    (corpus / "test_corpus.py").write_text("")

    paths = [p for p, _ in iter_test_files(tmp_path)]
    names = [p.name for p in paths]

    assert "test_real.py" in names
    assert "test_corpus.py" not in names
