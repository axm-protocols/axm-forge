"""Integration tests for axm_echo corpus extraction (real filesystem I/O)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _write_package(root: Path, name: str, module: str, body: str) -> Path:
    """Materialise a minimal real package tree on disk."""
    pkg = root / name / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / f"{module}.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return root / name


def test_extracts_public_symbols_via_ast(tmp_path: Path) -> None:
    """AC3, AC4: extract public symbols with qualname/signature/embed_text."""
    from axm_echo.corpus import extract_package

    pkg_root = _write_package(
        tmp_path,
        "sample-pkg",
        "errors",
        '''
        from __future__ import annotations


        def raise_rate_limit(retry_after: int) -> None:
            """Raise a rate limit error after the given delay."""
            raise RuntimeError(retry_after)


        def _private_helper() -> int:
            """Should not be extracted (private)."""
            return 0
        ''',
    )

    symbols = extract_package(pkg_root)

    by_name = {s["qualname"]: s for s in symbols}
    # Public symbol present, private excluded.
    assert any("raise_rate_limit" in q for q in by_name)
    assert not any("_private_helper" in q for q in by_name)

    entry = next(s for q, s in by_name.items() if "raise_rate_limit" in q)
    assert entry["package"]
    assert entry["signature"]
    assert entry["doc_first_line"]
    assert entry["embed_text"]
    # embed_text falls back to the docstring when present.
    assert "rate limit" in entry["embed_text"].lower()


def test_groundtruth_neighbors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1, AC3: semantically-close pair surfaces as a near neighbor (st)."""
    st = pytest.importorskip("sentence_transformers")
    assert st is not None

    from axm_echo import embed, extract_monorepo, neighbors

    _write_package(
        tmp_path,
        "pkg-a",
        "net",
        '''
        def raise_rate_limit_error() -> None:
            """Raise an error when the API rate limit is exceeded."""
        ''',
    )
    _write_package(
        tmp_path,
        "pkg-b",
        "throttle",
        '''
        def fail_on_quota_exceeded() -> None:
            """Raise an error when the request quota limit is exceeded."""
        ''',
    )
    _write_package(
        tmp_path,
        "pkg-c",
        "io",
        '''
        def read_csv_rows() -> None:
            """Read rows from a csv file into a list of dicts."""
        ''',
    )

    config_dir = tmp_path / ".axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{tmp_path}"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    symbols = extract_monorepo()
    texts = [s["embed_text"] for s in symbols]
    assert len(texts) >= 3

    matrix = embed(texts, backend="st")
    rate_idx = next(
        i for i, s in enumerate(symbols) if "raise_rate_limit_error" in s["qualname"]
    )
    quota_idx = next(
        i for i, s in enumerate(symbols) if "fail_on_quota_exceeded" in s["qualname"]
    )

    results = neighbors(matrix[rate_idx], matrix, k=2)
    neighbor_idxs = [idx for idx, _score in results]
    # The quota-exceeded symbol is the closest non-self neighbor.
    assert quota_idx in neighbor_idxs
