"""Bandit JSON must represent a completed security measurement."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from axm_audit.core.rules import security
from axm_audit.core.rules.security import SecurityRule

pytestmark = pytest.mark.integration


def test_real_bandit_reports_medium_and_high(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "sample.py").write_text(
        "import subprocess\n"
        "import urllib.request\n"
        "def run(command, url):\n"
        "    subprocess.call(command, shell=True)\n"
        "    return urllib.request.urlopen(url)\n"
    )

    def real_bandit(
        cmd: list[str], project_path: Path, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 -- fixed test interpreter and arguments
            [sys.executable, "-m", "bandit", *cmd[1:]],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )

    monkeypatch.setattr(security, "run_in_project", real_bandit)
    result = SecurityRule().check(tmp_path)
    assert result.details["high_count"] >= 1
    assert result.details["medium_count"] >= 1
    assert result.score < 100


@pytest.mark.parametrize("returncode", [0, 1])
@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "Working...\\n{}",
        "not json",
        "{}",
        "[]",
        '{"results":null}',
        '{"results":[{}]}',
        '{"results":[{"issue_severity":[]}]}',
        '{"results":[],"errors":[{"reason":"failed to parse"}]}',
        '{"results":[],"errors":null}',
    ],
)
def test_incomplete_bandit_output_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int, stdout: str
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "sample.py").write_text("x = 1\n")
    monkeypatch.setattr(
        security,
        "run_in_project",
        lambda *args, **kwargs: subprocess.CompletedProcess([], returncode, stdout, ""),
    )
    result = SecurityRule().check(tmp_path)
    assert not result.passed
    assert result.severity.value == "error"
    assert result.score == 0


def test_issue_exit_with_empty_results_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("x = 1\n")
    monkeypatch.setattr(
        security,
        "run_in_project",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 1, '{"results":[],"errors":[]}', ""
        ),
    )
    result = SecurityRule().check(tmp_path)
    assert not result.passed
    assert result.severity.value == "error"


def test_low_only_result_preserves_existing_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("x = 1\n")
    monkeypatch.setattr(
        security,
        "run_in_project",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 1, '{"results":[{"issue_severity":"LOW"}],"errors":[]}', ""
        ),
    )
    result = SecurityRule().check(tmp_path)
    assert result.passed
    assert result.score == 100


def test_bandit_error_exit_rejects_even_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "sample.py").write_text("x = 1\n")
    monkeypatch.setattr(
        security,
        "run_in_project",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 2, '{"results":[]}', "fatal"
        ),
    )
    result = SecurityRule().check(tmp_path)
    assert not result.passed
    assert result.severity.value == "error"


def test_valid_clean_report_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "sample.py").write_text("x = 1\n")
    monkeypatch.setattr(
        security,
        "run_in_project",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, json.dumps({"results": []}), ""
        ),
    )
    assert SecurityRule().check(tmp_path).score == 100
