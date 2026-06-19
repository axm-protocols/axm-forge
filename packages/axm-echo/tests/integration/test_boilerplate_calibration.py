"""E3bis boilerplate-filter calibration, validated on the real monorepo corpus.

The ticket (AXM-2171) is empirical: it pins the two boilerplate seuils
``min_repeat`` (corpus-frequency filter, ``generic_docs``) x the length floor
(``MIN_DOC_CHARS``) against the *real* cross-package corpus, so a regression in
either seuil is caught here rather than in the field.

These tests build a self-contained on-disk corpus that mirrors the real
monorepo's boilerplate shape (mass-recurring CLI/render promises vs unique
terse legit promises vs the ground-truth duplicates), point
``~/axm/echo.toml`` at it, and run the real ``EchoCodeTool`` pipeline
end to end via the deterministic ``tfidf`` backend (no neural extra).

test_spec named ``axm_echo.clustering.filter_boilerplate``; the real boilerplate
surface is ``axm_echo.cluster`` (``generic_docs`` + ``split_pairs`` +
``MIN_DOC_CHARS``), exercised through the public ``EchoCodeTool`` boundary.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# A single cohesive calibration scenario over the full EchoCodeTool pipeline; it
# intentionally spans more than one canonical symbol tuple.
pytestmark = [pytest.mark.integration, pytest.mark.scenario_name_ok]


def _write_package(root: Path, name: str, module: str, body: str) -> Path:
    """Materialise a minimal real package tree on disk; return its root."""
    pkg_root = root / "packages" / name
    pkg = pkg_root / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / f"{module}.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return pkg_root


def _point_scope_at(home: Path, monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make ``load_scope`` read a config whose only workspace root is ``root``."""
    config_dir = home / "axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root}"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))


def _qualnames(entries: list[dict[str, object]]) -> set[str]:
    """Project cluster entries onto the set of all member qualnames."""
    out: set[str] = set()
    for cluster in entries:
        members = cluster.get("members", [])
        assert isinstance(members, list)
        out |= {str(m["qualname"]) for m in members}
    return out


def _boilerplate_first_lines(result_data: dict[str, object]) -> set[str]:
    """First-lines of every symbol in the demoted boilerplate bucket."""
    pairs = result_data["boilerplate"]
    assert isinstance(pairs, list)
    lines: set[str] = set()
    for pair in pairs:
        for side in ("a", "b"):
            lines.add(str(pair[side]["doc_first_line"]).strip().lower())
    return lines


def test_terse_legit_doc_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: a unique terse promise is NOT demoted by the calibrated seuils.

    The POC lesson: a brute length filter wrongly dropped ``APIUnavailable``
    (38 chars). With ``MIN_DOC_CHARS=15`` as a floor and frequency as the real
    signal, a *unique* terse promise clusters as a genuine duplicate instead of
    landing in the boilerplate bucket.
    """
    from axm_echo.cluster import MIN_DOC_CHARS
    from axm_echo.tools import EchoCodeTool

    # 38-39 chars: longer than the floor, shorter than a verbose docstring.
    terse = '"""502/503/504 - service temporarily down."""'
    assert len("502/503/504 - service temporarily down.") > MIN_DOC_CHARS
    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-commons",
        "errors",
        f"""
        class APIUnavailable(Exception):
            {terse}
        """,
    )
    _write_package(
        ws,
        "axm-bib",
        "errors",
        f"""
        class APIUnavailable(Exception):
            {terse}
        """,
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    # The terse legit promise is a genuine cross-package echo, not boilerplate.
    assert "502/503/504 - service temporarily down." not in _boilerplate_first_lines(
        result.data
    )
    clustered = _qualnames(result.data["clusters"])
    assert any(q.endswith(".APIUnavailable") for q in clustered), (
        "a unique terse legit promise was wrongly dropped instead of clustered"
    )


def test_generic_main_demoted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC1: a first-line recurring across >= min_repeat symbols is boilerplate.

    ``CLI entry point.`` recurs 9x in the real corpus; the calibrated
    ``min_repeat`` (4) demotes any such mass-recurring promise to the
    boilerplate bucket rather than reporting it as a duplicate cluster.
    """
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    # Five cross-package CLI entry points -- above the calibrated min_repeat=4.
    for idx, pkg in enumerate(("axm-a", "axm-b", "axm-c", "axm-d", "axm-e")):
        _write_package(
            ws,
            pkg,
            "cli",
            f'''
            def main_{idx}() -> None:
                """CLI entry point."""
            ''',
        )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    # The recurring generic promise is demoted, never a duplicate cluster.
    assert "cli entry point." in _boilerplate_first_lines(result.data)
    leaked = any(
        q.split(".")[-1].startswith("main_")
        for q in _qualnames(result.data["clusters"])
    )
    assert not leaked, "recurring boilerplate leaked into a duplicate cluster"


def test_groundtruth_survives_calibration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: ground-truth duplicates stay clustered after calibration.

    ``RateLimitError`` and ``request_with_retry`` are the canonical genuine
    cross-package echoes; the calibrated boilerplate filter must not demote
    them -- they remain duplicate clusters even alongside recurring boilerplate.
    """
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-commons",
        "errors",
        '''
        class RateLimitError(Exception):
            """Raised when the upstream API rate limit has been exceeded."""
        ''',
    )
    _write_package(
        ws,
        "axm-bib",
        "errors",
        '''
        class RateLimitError(Exception):
            """Raised when the upstream API rate limit has been exceeded."""
        ''',
    )
    _write_package(
        ws,
        "axm-commons2",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    _write_package(
        ws,
        "axm-bib2",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    # Recurring boilerplate in the same corpus, to prove it does not bleed onto
    # the ground truth (both buckets coexist).
    for idx, pkg in enumerate(("axm-c", "axm-d", "axm-e", "axm-f")):
        _write_package(
            ws,
            pkg,
            "cli",
            f'''
            def main_{idx}() -> None:
                """CLI entry point."""
            ''',
        )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    clustered = _qualnames(result.data["clusters"])
    assert any("RateLimitError" in q for q in clustered), (
        "RateLimitError ground truth was demoted by calibration"
    )
    assert any("request_with_retry" in q for q in clustered), (
        "request_with_retry ground truth was demoted by calibration"
    )
    bucket = _boilerplate_first_lines(result.data)
    assert "raised when the upstream api rate limit has been exceeded." not in bucket
    assert (
        "perform an http request, retrying with backoff on transient errors."
        not in bucket
    )
