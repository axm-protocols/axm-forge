"""audit_test needs nothing but pytest in the target interpreter.

Real subprocesses against throw-away virtual environments built in a temp dir:
one with pytest only (no ``pytest-json-report``, no ``pytest-cov``), one with
no pytest at all. The target is reached the way a session reaches it, through a
declared runtime (``DependencyEnvironment``), where nothing may be installed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from axm import DependencyEnvironment
from axm.tools.dependency_reads import dependency_read_context
from axm.tools.write_scope import WriteContract

from axm_audit.core.test_runner import (
    FailureDetail,
    build_test_report,
    parse_json_report,
    run_tests,
)

pytestmark = pytest.mark.e2e

_SUITE = """
import pytest


@pytest.fixture
def broken_fixture():
    raise RuntimeError("fixture exploded")


def test_passes():
    assert 1 + 1 == 2


def test_fails_with_long_message():
    detail = "\\n".join(f"detail line {n}" for n in range(200))
    assert False, f"HEAD-MARKER\\n{detail}\\nTAIL-MARKER"


def test_errors_in_setup(broken_fixture):
    assert True


@pytest.mark.skip(reason="not today")
def test_skipped():
    assert False


@pytest.mark.parametrize("value", [1, 2, 3])
def test_parametrized(value):
    assert value != 2
"""

_BROKEN = (
    "import a_module_that_does_not_exist_anywhere\n\n\ndef test_never():\n    pass\n"
)


def _uv() -> str:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the throw-away environments"
    return uv


def _make_venv(root: Path, *, packages: list[str]) -> Path:
    venv = root / "venv"
    subprocess.run(  # noqa: S603
        [_uv(), "venv", "--python", sys.executable, str(venv)],
        check=True,
        capture_output=True,
    )
    python = venv / "bin" / "python"
    if packages:
        subprocess.run(  # noqa: S603
            [_uv(), "pip", "install", "--python", str(python), *packages],
            check=True,
            capture_output=True,
        )
    return python


def _imports(python: Path, module: str) -> bool:
    probe = (
        f"import importlib.util as u; raise SystemExit(u.find_spec({module!r}) is None)"
    )
    return subprocess.run([str(python), "-c", probe]).returncode == 0  # noqa: S603


@pytest.fixture(scope="module")
def pytest_only_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An interpreter with pytest and neither pytest-json-report nor pytest-cov."""
    python = _make_venv(tmp_path_factory.mktemp("pytest_only"), packages=["pytest"])
    assert _imports(python, "pytest")
    assert not _imports(python, "pytest_jsonreport")
    assert not _imports(python, "pytest_cov")
    return python


@pytest.fixture(scope="module")
def pytestless_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An interpreter with no pytest at all."""
    python = _make_venv(tmp_path_factory.mktemp("pytestless"), packages=[])
    assert not _imports(python, "pytest")
    return python


def _project(root: Path, source: str) -> Path:
    project = root / "project"
    (project / "tests").mkdir(parents=True)
    (project / "tests" / "test_sample.py").write_text(textwrap.dedent(source))
    return project


@pytest.fixture
def suite(tmp_path: Path) -> Path:
    return _project(tmp_path, _SUITE)


@pytest.fixture
def broken(tmp_path: Path) -> Path:
    return _project(tmp_path, _BROKEN)


@contextmanager
def _declared(python: Path, project: Path) -> Iterator[None]:
    """Bind the declared runtime a session gives: this interpreter, no installs."""
    env = DependencyEnvironment(str(python), str(project), ())
    with dependency_read_context(
        WriteContract(str(project), dependency_environment=env)
    ):
        yield


def test_pytest_only_interpreter_yields_the_complete_result(
    pytest_only_python: Path, suite: Path
) -> None:
    with _declared(pytest_only_python, suite):
        report = run_tests(suite, stop_on_first=False, include_cases=True)

    assert report.pytest_return_code == 1
    assert report.non_test_cause is None
    assert (report.passed, report.failed, report.errors, report.skipped) == (3, 2, 1, 1)
    assert report.collected == 7
    assert {case.node_id: case.outcome for case in report.cases} == {
        "tests/test_sample.py::test_passes": "passed",
        "tests/test_sample.py::test_fails_with_long_message": "failed",
        "tests/test_sample.py::test_errors_in_setup": "error",
        "tests/test_sample.py::test_skipped": "skipped",
        "tests/test_sample.py::test_parametrized[1]": "passed",
        "tests/test_sample.py::test_parametrized[2]": "failed",
        "tests/test_sample.py::test_parametrized[3]": "passed",
    }
    assert report.duration > 0
    assert report.verdict is False
    assert report.failures is not None
    assert {f.test for f in report.failures} == {
        "tests/test_sample.py::test_fails_with_long_message",
        "tests/test_sample.py::test_errors_in_setup",
        "tests/test_sample.py::test_parametrized[2]",
    }


def test_coverage_is_reported_unavailable_not_an_exit_4(
    pytest_only_python: Path, suite: Path
) -> None:
    with _declared(pytest_only_python, suite):
        full = run_tests(suite, stop_on_first=False)
        targeted = run_tests(
            suite,
            files=["tests/test_sample.py::test_passes"],
            stop_on_first=False,
        )

    assert full.pytest_return_code == 1
    assert full.passed == 3
    assert full.coverage is None
    assert full.coverage_unavailable is not None
    assert "pytest-cov" in full.coverage_unavailable
    assert "venv" in full.coverage_unavailable  # names the interpreter
    assert targeted.pytest_return_code == 0
    assert targeted.verdict is True
    assert targeted.coverage_unavailable is None  # coverage was not requested


def test_failure_excerpt_carries_head_and_tail_of_the_failure(
    pytest_only_python: Path, suite: Path
) -> None:
    with _declared(pytest_only_python, suite):
        report = run_tests(suite, stop_on_first=False)

    assert report.failures is not None
    failure = next(f for f in report.failures if "long_message" in f.test)
    lines = failure.traceback.splitlines()
    assert len(lines) >= 40
    assert len(failure.traceback) <= 6200
    assert any("lines elided" in line for line in lines)
    assert "test_sample.py" in failure.traceback  # the test's own frame (head)
    assert "TAIL-MARKER" in failure.traceback  # the assertion message (tail)
    assert "detail line 199" in failure.traceback
    assert "HEAD-MARKER" in failure.message


def test_collection_error_is_reported_with_its_cause(
    pytest_only_python: Path, broken: Path
) -> None:
    with _declared(pytest_only_python, broken):
        report = run_tests(broken, stop_on_first=False)

    assert report.pytest_return_code == 2
    assert report.collected == 0
    assert report.verdict is False
    assert report.failures is not None
    assert "a_module_that_does_not_exist_anywhere" in report.failures[0].traceback
    assert report.failures[0].test == "tests/test_sample.py"


def test_interpreter_without_pytest_is_a_typed_error(
    pytestless_python: Path, suite: Path
) -> None:
    from axm_audit.core.pytest_env import PytestEnvironmentError

    with (
        _declared(pytestless_python, suite),
        pytest.raises(PytestEnvironmentError) as raised,
    ):
        run_tests(suite)

    assert raised.value.missing == "pytest"
    assert "pytestless" in raised.value.interpreter
    assert "pytestless" in str(raised.value)
    assert "pytest is not installed" in str(raised.value)
    assert "unrecognized arguments" not in str(raised.value)


def test_target_environment_is_left_untouched(
    pytest_only_python: Path, suite: Path
) -> None:
    site = pytest_only_python.parent.parent
    before = sorted(
        str(p.relative_to(site))
        for p in site.rglob("*")
        if "__pycache__" not in p.parts and p.is_file()
    )
    with _declared(pytest_only_python, suite):
        run_tests(suite, stop_on_first=False)
    after = sorted(
        str(p.relative_to(site))
        for p in site.rglob("*")
        if "__pycache__" not in p.parts and p.is_file()
    )
    assert after == before


def test_result_matches_the_pytest_json_report_path_where_both_exist(
    suite: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same content as the historical ``pytest-json-report`` path.

    This test's own interpreter has both plugins, so the two paths can be run
    side by side on the same suite.
    """
    old_json = tmp_path / "old.json"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--json-report",
            f"--json-report-file={old_json}",
            "--json-report-omit=log,keywords",
            "--tb=short",
            "--no-header",
            "-q",
            "tests",
        ],
        cwd=suite,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_ADDOPTS": ""},
    )
    old = build_test_report(
        report_data=parse_json_report(old_json),
        total_cov=None,
        per_file_cov={},
        include_cases=True,
    )

    # pytest-json-report is installed here, yet the new path must not need it:
    # disable it for the target session (a real run would fail on `--json-report`).
    monkeypatch.setenv("PYTEST_ADDOPTS", "-p no:jsonreport")
    with _declared(Path(sys.executable), suite):
        new = run_tests(suite, stop_on_first=False, include_cases=True)

    assert (new.passed, new.failed, new.errors, new.skipped) == (
        old.passed,
        old.failed,
        old.errors,
        old.skipped,
    )
    assert new.cases == old.cases
    assert [(c.node_id, c.detail is None) for c in new.cases] == [
        (c.node_id, c.detail is None) for c in old.cases
    ]
    assert old.failures is not None
    assert new.failures is not None

    def identity(failures: list[FailureDetail]) -> list[tuple[object, ...]]:
        return [(f.test, f.error_type, f.message, f.file, f.line) for f in failures]

    assert identity(new.failures) == identity(old.failures)
    # what the old path kept was the last 5 lines: the new excerpt ends the same.
    for new_failure, old_failure in zip(new.failures, old.failures, strict=True):
        assert new_failure.traceback.endswith(old_failure.traceback)


def test_report_file_is_written_by_the_plugin_alone(
    pytest_only_python: Path, suite: Path, tmp_path: Path
) -> None:
    """The plugin loads by ``-p`` + PYTHONPATH and writes the documented JSON."""
    from axm_audit.core.pytest_env import PLUGIN_DIR, PLUGIN_MODULE

    out = tmp_path / "plugin.json"
    result = subprocess.run(  # noqa: S603
        [
            str(pytest_only_python),
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-p",
            PLUGIN_MODULE,
            f"--axm-report-file={out}",
            "tests",
        ],
        cwd=suite,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PLUGIN_DIR)},
    )
    assert result.returncode == 1, result.stdout + result.stderr
    data = json.loads(out.read_text())
    assert data["summary"]["collected"] == 7
    assert data["summary"]["passed"] == 3
    assert {t["nodeid"] for t in data["tests"]} >= {
        "tests/test_sample.py::test_parametrized[1]"
    }
