"""Unit tests for PyramidLevelRule R4 (conftest fixture IO) and R5.

Covers mock neutralization.

Spec: AXM-1502 — PyramidLevelRule v6 R4/R5 implementation.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from axm_audit.core.rules.test_quality import _shared
from axm_audit.core.rules.test_quality.pyramid_level import PyramidLevelRule


@pytest.fixture(autouse=True)
def _clear_conftest_cache() -> None:
    """Ensure each test starts with an empty conftest cache."""
    cache = getattr(_shared, "_CONFTEST_CACHE", None)
    if isinstance(cache, dict):
        cache.clear()


def _make_pkg(
    tmp_path: Path,
    test_source: str,
    conftest_source: str = "",
    test_subdir: str = "integration",
) -> Path:
    """Build a minimal package layout: src/pkg + tests/<subdir>/test_sample.py.

    ``test_subdir`` places the test file — default ``integration`` so that
    real-IO classifications are not flagged as location mismatches by R2.
    """
    pkg = tmp_path / "pkg"
    src = pkg / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("")
    (src / "mod.py").write_text(
        "import httpx\n\ndef run():\n    return httpx.get('http://x')\n"
    )

    tests = pkg / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")

    sub = tests / test_subdir
    sub.mkdir()
    (sub / "__init__.py").write_text("")

    if conftest_source:
        (tests / "conftest.py").write_text(
            textwrap.dedent(conftest_source).lstrip("\n")
        )

    (sub / "test_sample.py").write_text(textwrap.dedent(test_source).lstrip("\n"))
    return pkg


def _find(pkg: Path, func_name: str = "test_foo"):
    findings = PyramidLevelRule().check(pkg).findings
    for f in findings:
        if f.function == func_name:
            return f
    raise AssertionError(
        f"No finding for {func_name}; got {[(x.function, x.level) for x in findings]}"
    )


# ---------------------------------------------------------------------------
# R4 — conftest fixture IO
# ---------------------------------------------------------------------------


def test_r4_conftest_fixture_with_write_text_detected(tmp_path: Path) -> None:
    """AC1/AC2: conftest fixture that performs write_text is detected."""
    conftest = """
        import pytest

        @pytest.fixture
        def pkg_dir(tmp_path):
            tmp_path.write_text("x")
            return tmp_path
        """
    test = """
        def test_foo(pkg_dir):
            assert pkg_dir
        """
    pkg = _make_pkg(tmp_path, test, conftest_source=conftest)
    finding = _find(pkg)
    assert finding.level == "integration"
    assert any(
        sig.startswith("conftest-fixture-io:pkg_dir") for sig in finding.io_signals
    ), finding.io_signals


def test_r4_conftest_cache_not_re_parsed(tmp_path: Path, mocker) -> None:
    """AC1: _CONFTEST_CACHE prevents re-parsing the same conftest file."""
    conftest_path = tmp_path / "conftest.py"
    conftest_path.write_text(
        textwrap.dedent(
            """
            import pytest

            @pytest.fixture
            def pkg_dir(tmp_path):
                tmp_path.write_text("x")
                return tmp_path
            """
        ).lstrip("\n")
    )

    load = getattr(_shared, "_load_conftest_fixtures", None)
    if load is None:
        pytest.skip("_load_conftest_fixtures not exposed on _shared")

    spy = mocker.spy(Path, "read_text")
    load(conftest_path)
    load(conftest_path)

    # Count calls that targeted our conftest path.
    calls = [c for c in spy.call_args_list if c.args and c.args[0] == conftest_path]
    assert len(calls) == 1, f"expected 1 read, got {len(calls)}"


def test_r4_transitive_fixture_dep(tmp_path: Path) -> None:
    """AC2: fixture_a -> fixture_b -> tmp_path write is detected via fixture_a."""
    conftest = """
        import pytest

        @pytest.fixture
        def fixture_b(tmp_path):
            tmp_path.write_text("x")
            return tmp_path

        @pytest.fixture
        def fixture_a(fixture_b):
            return fixture_b
        """
    test = """
        def test_foo(fixture_a):
            assert fixture_a
        """
    pkg = _make_pkg(tmp_path, test, conftest_source=conftest)
    finding = _find(pkg)
    assert finding.level == "integration"
    assert any("conftest-fixture-io:fixture_a" in sig for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r4_depth_guard_at_3(tmp_path: Path) -> None:
    """AC2: depth > 3 fixture chain is NOT resolved (guard)."""
    conftest = """
        import pytest

        @pytest.fixture
        def fix_d(tmp_path):
            tmp_path.write_text("x")
            return tmp_path

        @pytest.fixture
        def fix_c(fix_d):
            return fix_d

        @pytest.fixture
        def fix_b(fix_c):
            return fix_c

        @pytest.fixture
        def fix_a(fix_b):
            return fix_b
        """
    test = """
        def test_foo(fix_a):
            assert fix_a
        """
    pkg = _make_pkg(tmp_path, test, conftest_source=conftest, test_subdir="unit")
    finding = _find(pkg)
    assert not any(
        sig.startswith("conftest-fixture-io:fix_a") for sig in finding.io_signals
    ), finding.io_signals


def test_r4_skipped_when_r3_attr_present(tmp_path: Path) -> None:
    """AC3: R4 does not fire when R3 attr-scan already flagged real_io."""
    conftest = """
        import pytest

        @pytest.fixture
        def pkg_dir(tmp_path):
            tmp_path.write_text("x")
            return tmp_path
        """
    test = """
        def test_foo(pkg_dir, tmp_path):
            tmp_path.mkdir(exist_ok=True)
            assert pkg_dir
        """
    pkg = _make_pkg(tmp_path, test, conftest_source=conftest)
    finding = _find(pkg)
    conftest_sigs = [
        s for s in finding.io_signals if s.startswith("conftest-fixture-io")
    ]
    assert len(conftest_sigs) <= 1, f"duplicate conftest signals: {conftest_sigs}"


# ---------------------------------------------------------------------------
# R5 — mock neutralization
# ---------------------------------------------------------------------------


def test_r5_soft_only_with_mock_httpx_becomes_unit(tmp_path: Path) -> None:
    """AC4/AC5/AC8: soft signals + mock on httpx -> unit.

    Signal mock-neutralized:* emitted.
    """
    test = """
        from unittest.mock import patch
        import httpx

        def test_foo():
            with patch("pkg.mod.httpx"):
                httpx
        """
    pkg = _make_pkg(tmp_path, test, test_subdir="unit")
    finding = _find(pkg)
    assert finding.level == "unit", (finding.level, finding.io_signals)
    assert any(sig.startswith("mock-neutralized:") for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_hard_writer_with_mock_stays_integration(tmp_path: Path) -> None:
    """AC6 (hard invariant A): write_text present -> R5 never flips to unit."""
    test = """
        from unittest.mock import patch

        def test_foo(tmp_path):
            with patch("httpx.get"):
                tmp_path.write_text("x")
        """
    pkg = _make_pkg(tmp_path, test)
    finding = _find(pkg)
    assert finding.level == "integration", (finding.level, finding.io_signals)
    assert not any(sig.startswith("mock-neutralized") for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_tmp_path_write_read_with_mock_stays_integration(tmp_path: Path) -> None:
    """AC6: tmp_path+write/read hard signal -> integration even with patch()."""
    test = """
        from unittest.mock import patch

        def test_foo(tmp_path):
            with patch("pkg.mod.httpx"):
                p = tmp_path / "x.txt"
                p.write_text("hi")
                p.read_text()
        """
    pkg = _make_pkg(tmp_path, test)
    finding = _find(pkg)
    assert finding.level == "integration", (finding.level, finding.io_signals)


def test_r5_subprocess_with_mock_stays_e2e(tmp_path: Path) -> None:
    """AC7 (hard invariant B): subprocess/CliRunner -> R5 NEVER fires."""
    test = """
        from unittest.mock import patch
        import subprocess

        def test_foo():
            with patch("pkg.mod.run"):
                subprocess.run(["echo", "hi"], check=True)
        """
    pkg = _make_pkg(tmp_path, test, test_subdir="e2e")
    finding = _find(pkg)
    assert finding.level == "e2e", (finding.level, finding.io_signals)
    assert not any(sig.startswith("mock-neutralized") for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_patch_object_recognised_target(tmp_path: Path) -> None:
    """AC5: patch.object(subprocess, 'run') extracts target.

    Extracts subprocess.run & neutralizes.
    """
    test = """
        from unittest.mock import patch
        import subprocess

        def test_foo():
            with patch.object(subprocess, "run"):
                pass
        """
    pkg = _make_pkg(tmp_path, test, test_subdir="unit")
    finding = _find(pkg)
    assert finding.level == "unit", (finding.level, finding.io_signals)
    assert any("mock-neutralized" in sig for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_monkeypatch_setattr_recognised(tmp_path: Path) -> None:
    """AC5: monkeypatch.setattr('pkg.mod.run', X) is recognised as an IO target."""
    test = """
        import subprocess

        def test_foo(monkeypatch):
            monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
        """
    pkg = _make_pkg(tmp_path, test, test_subdir="unit")
    finding = _find(pkg)
    assert finding.level == "unit", (finding.level, finding.io_signals)
    assert any("mock-neutralized" in sig for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_mock_factory_with_soft_signals_neutralizes(tmp_path: Path) -> None:
    """AC5: MagicMock() factory + only soft signals.

    Expects mock-factory:MagicMock neutralization.
    """
    test = """
        from unittest.mock import MagicMock
        import httpx

        def test_foo():
            client = MagicMock()
            client.get("http://x")
            httpx
        """
    pkg = _make_pkg(tmp_path, test, test_subdir="unit")
    finding = _find(pkg)
    assert finding.level == "unit", (finding.level, finding.io_signals)
    assert any("mock-factory" in sig for sig in finding.io_signals), finding.io_signals


def test_r5_no_mock_at_all_stays_integration(tmp_path: Path) -> None:
    """AC4: soft signals but no mock anywhere -> no neutralization."""
    test = """
        import httpx

        def test_foo():
            httpx.get("http://x")
        """
    pkg = _make_pkg(tmp_path, test)
    finding = _find(pkg)
    assert finding.level == "integration", (finding.level, finding.io_signals)
    assert not any(sig.startswith("mock-neutralized") for sig in finding.io_signals), (
        finding.io_signals
    )


def test_r5_target_not_matching_io_does_not_neutralize(tmp_path: Path) -> None:
    """AC5: patch('pkg.mod.helper') where helper is not IO.

    Non-IO target -> no neutralization.
    """
    test = """
        from unittest.mock import patch
        import httpx

        def test_foo():
            with patch("pkg.mod.helper"):
                httpx.get("http://x")
        """
    pkg = _make_pkg(tmp_path, test)
    finding = _find(pkg)
    assert finding.level == "integration", (finding.level, finding.io_signals)
    assert not any(sig.startswith("mock-neutralized") for sig in finding.io_signals), (
        finding.io_signals
    )
