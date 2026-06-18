"""Integration tests for the ``echo_check`` AXMTool (real FS + corpus walk).

Each test materialises a self-contained corpus on disk, points
``~/.axm/echo.toml`` at it, and runs the real :class:`~axm_echo.tools.EchoCheckTool`
end to end: it embeds the supplied *intention*, retrieves the top-k nearest
candidates across the whole monorepo, and tags each with a location verdict
(canonical / reuse-in-place / promote).

Semantic ground-truth (AC5) needs the neural ``st`` backend, so it
``importorskip``s ``sentence_transformers`` -- it only runs when the optional
``neural`` extra is installed. The structural verdict and the no-candidate
cases run deterministically on the ``tfidf`` backend (no torch).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# A cohesive intent-retrieval scenario exercising the full EchoCheckTool
# pipeline (corpus -> embed -> neighbors -> verdict) on a real tree; it spans
# more than one canonical symbol tuple.
pytestmark = [pytest.mark.integration, pytest.mark.scenario_name_ok]


def _write_package(root: Path, name: str, module: str, body: str) -> Path:
    """Materialise a minimal real package tree on disk; return its root.

    Packages live under the canonical ``<workspace_root>/packages/<pkg>``
    convention (the scope lists the workspace root directly).
    """
    pkg_root = root / "packages" / name
    pkg = pkg_root / "src" / name.replace("-", "_")
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / f"{module}.py").write_text(textwrap.dedent(body), encoding="utf-8")
    return pkg_root


def _point_scope_at(home: Path, monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make ``load_scope`` read a config whose only workspace root is ``root``."""
    config_dir = home / ".axm"
    config_dir.mkdir()
    (config_dir / "echo.toml").write_text(
        f'workspace_roots = ["{root}"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))


def _candidate_names(candidates: list[dict[str, object]]) -> list[str]:
    """Project candidates onto their bare symbol names, ranking order preserved."""
    return [str(c["name"]) for c in candidates]


def test_http_retry_intent_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: intention \"HTTP request with retry/backoff\" surfaces request_with_retry.

    Success criterion #2: the semantic backend must rank ``request_with_retry``
    as a top candidate, even though the intention text shares no tokens with
    the symbol name. This is the genuinely neural case, hence the importorskip.
    """
    pytest.importorskip("sentence_transformers")
    from axm_echo.tools import EchoCheckTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-commons",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    _write_package(
        ws,
        "axm-other",
        "text",
        '''
        def slugify(value: str) -> str:
            """Lowercase a string and replace spaces with hyphens for a slug."""
            return value
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCheckTool().execute(
        intention="HTTP request with retry and exponential backoff"
    )

    assert result.success, result.error
    candidates = result.data["candidates"]
    assert candidates, "no candidate retrieved for the HTTP-retry intention"
    # request_with_retry must be the top candidate (success criterion #2).
    assert candidates[0]["name"] == "request_with_retry"
    # Retrieval returns the candidate docstring so the agent can decide.
    assert candidates[0]["doc_first_line"]


def test_reuse_in_place_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: a candidate found outside axm-ingot gets the reuse-in-place verdict.

    The key value of echo_check: a helper that lives in a regular package
    (not yet canonicalised into axm-ingot) must be flagged \"reuse in place
    from <pkg>\" -- never silently treated as absent and never forced into a
    promotion ticket.
    """
    from axm_echo.tools import EchoCheckTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-bib",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCheckTool().execute(
        intention="Perform an HTTP request, retrying with backoff on transient errors",
        backend="tfidf",
    )

    assert result.success, result.error
    candidates = result.data["candidates"]
    match = next((c for c in candidates if c["name"] == "request_with_retry"), None)
    assert match is not None, "the in-place helper was not retrieved"
    # It lives in axm-bib (not axm-ingot), so the verdict is reuse-in-place...
    assert match["verdict"] == "reuse_in_place"
    assert match["package"] == "axm-bib"
    # ...and the text report names the originating package.
    assert result.text is not None
    assert "axm-bib" in result.text


def test_novel_intent_no_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: a novel intention with no equivalent yields no false reuse verdict.

    Retrieval is a *score*, not a decision: when nothing in the corpus is
    close, the top-k must be empty (or low-scoring) and no candidate may carry
    a reuse verdict -- the agent must not be told to reuse something absent.
    """
    from axm_echo.tools import EchoCheckTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-bib",
        "net",
        '''
        def request_with_retry(url: str) -> bytes:
            """Perform an HTTP request, retrying with backoff on transient errors."""
            return b""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCheckTool().execute(
        intention="Render a mermaid sequence diagram from a graph definition",
        backend="tfidf",
    )

    assert result.success, result.error
    # No token overlap with the only corpus symbol -> nothing close enough to
    # cross the retrieval threshold: top-k is empty.
    assert result.data["candidates"] == []
    # And nothing is reported as reusable.
    assert not any(
        "reuse" in str(c.get("verdict", "")) for c in result.data["candidates"]
    )
