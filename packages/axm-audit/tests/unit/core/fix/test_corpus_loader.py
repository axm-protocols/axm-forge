"""AC1, AC4, AC8: fix corpus loader smoke tests."""

from __future__ import annotations

from pathlib import Path


def test_load_relocate_only_fixture() -> None:
    """AC4, AC8: factory returns paths to existing tmp_pkg and expected tree."""
    from tests.fixtures.fix_corpus.conftest import fix_corpus_case

    tmp_pkg, expected_path = fix_corpus_case("relocate_only")

    assert tmp_pkg.exists()
    assert (tmp_pkg / "pyproject.toml").exists()
    assert isinstance(expected_path, Path)
    assert "fix_corpus/relocate_only/expected" in expected_path.as_posix()


def test_corpus_root_has_six_cases() -> None:
    """AC1: corpus root has exactly 6 named sub-dirs with input/ and expected/."""
    corpus_root = Path(__file__).parents[3] / "fixtures" / "fix_corpus"

    expected_names = {
        "relocate_only",
        "split_only",
        "merge_only",
        "rename_only",
        "flatten_only",
        "mixed",
    }
    actual_names = {
        p.name
        for p in corpus_root.iterdir()
        if p.is_dir() and not p.name.startswith("__")
    }

    assert actual_names == expected_names

    for name in expected_names:
        case_dir = corpus_root / name
        assert (case_dir / "input").is_dir(), f"{name}/input missing"
        assert (case_dir / "expected").is_dir(), f"{name}/expected missing"
