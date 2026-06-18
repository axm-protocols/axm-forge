"""Integration tests for the ``echo_code`` AXMTool (real FS + neural backend).

These build a self-contained corpus on disk reproducing the textbook
cross-package duplications and the anti-signal cases, point
``~/.axm/echo.toml`` at it, and run the real ``EchoCodeTool`` end to end.

Since AXM-2188, ``torch`` is a BASE dependency of axm-echo: the neural ``st``
(MiniLM) clustering backend runs in-process by default, with no
``importorskip`` guard and no out-of-process subprocess. The structural /
anti-signal cases still use the cheaper ``tfidf`` backend.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# A cohesive echo-detection scenario exercising the full EchoCodeTool pipeline
# (corpus -> embed -> cross_pairs -> anti-signals -> clusters) on a real tree;
# it intentionally spans more than one canonical symbol tuple.
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


def _cluster_qualnames(clusters: list[dict[str, object]]) -> list[set[str]]:
    """Project each cluster onto the set of member qualnames."""
    out: list[set[str]] = []
    for cluster in clusters:
        members = cluster.get("members", [])
        assert isinstance(members, list)
        out.append({str(m["qualname"]) for m in members})
    return out


def test_tfidf_clusters_ratelimiterror_cross_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC1, AC2, AC4: full pipeline clusters a cross-package echo (tfidf path).

    Deterministic, no neural extra: the tfidf backend always resolves, so this
    exercises the whole ``EchoCodeTool`` pipeline (corpus -> embed -> pairs ->
    anti-signals -> clusters -> render) and the AC4 ground-truth shape without
    requiring torch.
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
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    assert result.data["corpus_size"] == 2
    rate_clusters = [
        c
        for c in _cluster_qualnames(result.data["clusters"])
        if any("RateLimitError" in q for q in c)
    ]
    assert rate_clusters, "RateLimitError was not clustered cross-package"
    # The compact text report names the tool and the cluster count.
    assert result.text is not None
    assert "echo_code" in result.text
    assert "cluster" in result.text.lower()


def test_tfidf_filters_trivial_accessors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3 (tfidf): trivial accessors never form a cluster."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-alpha",
        "models",
        '''
        def name(self) -> str:
            """Return the name."""
            return self._name
        ''',
    )
    _write_package(
        ws,
        "axm-beta",
        "models",
        '''
        def name(self) -> str:
            """Return the name."""
            return self._name
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    # Both accessors are filtered up front, so the corpus collapses below the
    # comparison floor and no clusters are produced.
    assert not any(
        any(q.endswith(".name") for q in c)
        for c in _cluster_qualnames(result.data["clusters"])
    )


def test_tfidf_demotes_parallel_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3 (tfidf): excel_*/word_* land in parallel_api, not clusters."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-excel",
        "render",
        '''
        def excel_export(path: str) -> None:
            """Export the active document to a file on disk at the given path."""
        ''',
    )
    _write_package(
        ws,
        "axm-word",
        "render",
        '''
        def word_export(path: str) -> None:
            """Export the active document to a file on disk at the given path."""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    leaked = any(
        any("excel_export" in q for q in c) and any("word_export" in q for q in c)
        for c in _cluster_qualnames(result.data["clusters"])
    )
    assert not leaked, "parallel-API pair leaked into duplicate clusters"
    parallel_names = {
        n
        for pair in result.data["parallel_api"]
        for n in (pair["a"]["name"], pair["b"]["name"])
    }
    assert {"excel_export", "word_export"} <= parallel_names


def test_empty_corpus_returns_no_clusters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corpus with fewer than two documented symbols yields no clusters."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-solo",
        "mod",
        '''
        def only_one() -> None:
            """The single documented symbol in the whole corpus."""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf")

    assert result.success, result.error
    assert result.data["clusters"] == []
    assert result.text is not None
    assert "echo_code" in result.text


def _forbid_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any out-of-process fork raise (AC3/AC4 — embedding stays in-process).

    Patches the ``subprocess`` module surface itself so *any* module reaching
    for ``run``/``Popen``/``call`` during embedding is caught, regardless of how
    it imported subprocess.
    """
    import subprocess

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("echo forked an out-of-process subprocess")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)
    monkeypatch.setattr(subprocess, "check_call", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)


def test_neural_clusters_no_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3, AC4: the default neural backend clusters in-process, no subprocess.

    With ``torch`` in base, ``EchoCodeTool`` clusters with the neural ``st``
    backend by default (no explicit ``backend=`` arg). It must embed entirely
    in-process -- any out-of-process fork (the abandoned ``python -c`` path)
    raises. The cross-package ``RateLimitError`` echo is still detected.
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
    _point_scope_at(home, monkeypatch, ws)

    _forbid_subprocess(monkeypatch)
    result = EchoCodeTool().execute()

    assert result.success, result.error
    rate_clusters = [
        c
        for c in _cluster_qualnames(result.data["clusters"])
        if any("RateLimitError" in q for q in c)
    ]
    assert rate_clusters, "neural default did not cluster RateLimitError"


def test_groundtruth_ratelimiterror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: ``RateLimitError`` is clustered cross-package on its docstring.

    Torch is in base since AXM-2188, so the neural path runs directly.
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
        "axm-other",
        "io",
        '''
        def read_csv_rows() -> None:
            """Read rows from a csv file into a list of dictionaries."""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute()

    assert result.success, result.error
    clusters = result.data["clusters"]
    rate_clusters = [
        c for c in _cluster_qualnames(clusters) if any("RateLimitError" in q for q in c)
    ]
    assert rate_clusters, "RateLimitError was not clustered cross-package"
    # The cluster spans both packages (it is a cross-package echo).
    members = next(
        c["members"]
        for c in clusters
        if any("RateLimitError" in str(m["qualname"]) for m in c["members"])
    )
    packages = {m["package"] for m in members}
    assert {"axm-commons", "axm-bib"} <= packages


def test_groundtruth_request_with_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4: ``request_with_retry`` is clustered cross-package on its docstring.

    Torch is in base since AXM-2188, so the neural path runs directly.
    """
    from axm_echo.tools import EchoCodeTool

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
        "axm-bib",
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

    result = EchoCodeTool().execute()

    assert result.success, result.error
    clusters = _cluster_qualnames(result.data["clusters"])
    retry_clusters = [c for c in clusters if any("request_with_retry" in q for q in c)]
    assert retry_clusters, "request_with_retry was not clustered cross-package"
    # Members come from two distinct packages.
    qualnames = retry_clusters[0]
    assert len(qualnames) >= 2


def test_trivial_accessors_filtered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC3: trivial accessors are filtered out and never form a cluster.

    Torch is in base since AXM-2188, so the neural path runs directly.
    """
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    # Two cross-package trivial accessors with the same boilerplate promise.
    _write_package(
        ws,
        "axm-alpha",
        "models",
        '''
        def name(self) -> str:
            """Return the name."""
            return self._name
        ''',
    )
    _write_package(
        ws,
        "axm-beta",
        "models",
        '''
        def name(self) -> str:
            """Return the name."""
            return self._name
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute()

    assert result.success, result.error
    clusters = _cluster_qualnames(result.data["clusters"])
    # The trivial accessor must not appear in any duplicate cluster.
    assert not any(any(q.endswith(".name") for q in c) for c in clusters), (
        "trivial accessor leaked into a cluster"
    )


def test_parallel_api_demoted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3: name-parallel API pairs (excel_*/word_*) are demoted, not duplicates.

    Torch is in base since AXM-2188, so the neural path runs directly.
    """
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _write_package(
        ws,
        "axm-excel",
        "render",
        '''
        def excel_export(path: str) -> None:
            """Export the active document to a file on disk at the given path."""
        ''',
    )
    _write_package(
        ws,
        "axm-word",
        "render",
        '''
        def word_export(path: str) -> None:
            """Export the active document to a file on disk at the given path."""
        ''',
    )
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute()

    assert result.success, result.error
    duplicate_clusters = _cluster_qualnames(result.data["clusters"])
    # The excel_/word_ parallel pair must not be reported as a duplicate cluster.
    leaked = any(
        any("excel_export" in q for q in c) and any("word_export" in q for q in c)
        for c in duplicate_clusters
    )
    assert not leaked, "parallel-API pair leaked into duplicate clusters"
    # It is recorded in the demoted parallel-API bucket instead.
    parallel = result.data["parallel_api"]
    parallel_names = {
        n for pair in parallel for n in (pair["a"]["name"], pair["b"]["name"])
    }
    assert {"excel_export", "word_export"} <= parallel_names


# Disjoint vocabularies, one per pair, so each pair forms its OWN cluster under
# tfidf (shared vocabulary across pairs would collapse them into one component).
_TOPICS = [
    "Reconcile the quarterly ledger across settlement counterparties.",
    "Render a heatmap of telemetry latency percentiles over time.",
    "Validate passport visa entries against the immigration registry.",
    "Compress raw seismograph waveforms with wavelet quantization.",
    "Translate culinary recipes between metric and imperial measures.",
    "Schedule orbital satellite handover during eclipse windows.",
    "Diagnose turbine vibration harmonics from accelerometer traces.",
    "Index herbarium specimens by taxonomic genus and collection date.",
    "Encrypt courier manifests with rotating elliptic-curve keypairs.",
    "Forecast reservoir inflow from upstream snowpack melt curves.",
]


def _twin_packages(ws: Path, n_pairs: int) -> None:
    """Write n_pairs of cross-package duplicate symbols, each its own echo.

    Each pair gets a topic with a disjoint vocabulary, so the two members of a
    pair match each other (a cross-package echo) while distinct pairs stay below
    the comparison threshold and form separate clusters.
    """
    for k in range(n_pairs):
        doc = _TOPICS[k % len(_TOPICS)]
        body = f'''
        def fn_{k}() -> None:
            """{doc}"""
        '''
        _write_package(ws, f"axm-left{k}", f"mod{k}", body)
        _write_package(ws, f"axm-right{k}", f"mod{k}", body)


def test_top_n_bounds_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC2: the report shows at most top_n clusters; the total count stays visible."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _twin_packages(ws, 8)
    _point_scope_at(home, monkeypatch, ws)

    result = EchoCodeTool().execute(backend="tfidf", threshold=0.5, top_n=3)

    assert result.success, result.error
    assert len(result.data["clusters"]) == 3
    assert result.data["cluster_count"] >= 8
    assert result.data["shown_count"] == 3


def test_waiver_excludes_then_converges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC4, AC6: an acknowledged cluster is excluded; a re-run re-centers."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _twin_packages(ws, 4)
    _point_scope_at(home, monkeypatch, ws)

    first = EchoCodeTool().execute(backend="tfidf", threshold=0.5, top_n=30)
    assert first.success, first.error
    baseline = first.data["cluster_count"]
    assert baseline >= 1
    waived = str(first.data["clusters"][0]["cluster_hash"])

    # Acknowledge the top cluster in the scan-root pyproject, then re-run.
    (ws / "pyproject.toml").write_text(
        "[[tool.axm-echo.acknowledged]]\n"
        f'hash = "{waived}"\n'
        'reason = "parallel API, intended cross-package duplication"\n',
        encoding="utf-8",
    )

    second = EchoCodeTool().execute(backend="tfidf", threshold=0.5, top_n=30)

    assert second.success, second.error
    shown_hashes = {c.get("cluster_hash") for c in second.data["clusters"]}
    assert waived not in shown_hashes
    assert second.data["actionable_count"] == baseline - 1


def test_stale_waiver_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC5: a waiver matching no live cluster is reported as stale, never blocks."""
    from axm_echo.tools import EchoCodeTool

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    home.mkdir()
    _twin_packages(ws, 2)
    _point_scope_at(home, monkeypatch, ws)

    (ws / "pyproject.toml").write_text(
        "[[tool.axm-echo.acknowledged]]\n"
        'hash = "deadbeef0000"\n'
        'reason = "removed long ago, this waiver should be retired"\n',
        encoding="utf-8",
    )

    result = EchoCodeTool().execute(backend="tfidf", threshold=0.5)

    assert result.success, result.error
    stale_hashes = {entry["hash"] for entry in result.data["stale_acknowledged"]}
    assert "deadbeef0000" in stale_hashes
