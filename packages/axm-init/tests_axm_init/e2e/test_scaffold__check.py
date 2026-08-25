"""E2E tests: ``axm-init scaffold`` then ``axm-init check`` via subprocess."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from axm_init.tools.scaffold import InitScaffoldTool

pytestmark = pytest.mark.e2e

PACKAGING_CHECK_IDS = frozenset(
    {
        "pyproject.pyproject_exists",
        "structure.src_layout",
        "structure.py_typed",
        "structure.tests_dir",
        "docs.mkdocs_exists",
    }
)

SCAFFOLD_IDENTITY = {
    "org": "DemoOrg",
    "author": "Demo Author",
    "email": "demo@example.com",
}

RESEARCH_FILENAME = "RESEARCH.md"
RESEARCH_CHECK_ID = "paper.research_present"


def test_scaffold_then_check_scores_100(tmp_path: Path) -> None:
    """AC3: a fresh scaffold scores exactly 100 and exits 0."""
    project = tmp_path / "demo-pkg"
    project.mkdir()

    scaffold = subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "scaffold",
            str(project),
            "--org",
            "DemoOrg",
            "--author",
            "Demo Author",
            "--email",
            "demo@example.com",
            "--license",
            "MIT",
            "--description",
            "demo package",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert scaffold.returncode == 0, scaffold.stderr

    check = subprocess.run(
        ["uv", "run", "axm-init", "check", str(project), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    # AC3: a fresh scaffold must score exactly 100 and exit 0 — no longer
    # tolerate ``returncode in (0, 1)`` without a score constraint.
    assert check.returncode == 0, check.stderr
    report = json.loads(check.stdout)
    assert report["score"] == 100, report.get("failures", report)


def _run_scaffold(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``axm-init scaffold`` as a subprocess with the shared identity."""
    return subprocess.run(
        [
            "uv",
            "run",
            "axm-init",
            "scaffold",
            *args,
            "--org",
            "DemoOrg",
            "--author",
            "Demo Author",
            "--email",
            "demo@example.com",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_scaffold_paper_into_empty_directory(tmp_path: Path) -> None:
    """AC1: ``scaffold --kind paper`` exits 0 and writes the plan file."""
    paper = tmp_path / "demo-paper"
    paper.mkdir()

    scaffold = _run_scaffold(str(paper), "--kind", "paper", "--json")

    assert scaffold.returncode == 0, scaffold.stderr
    plans = [p for p in paper.rglob("*.md") if "plan" in p.name.lower()]
    assert plans, sorted(str(p.relative_to(paper)) for p in paper.rglob("*"))


def test_scaffold_experiment_inside_paper_json(tmp_path: Path) -> None:
    """AC5: ``scaffold --kind experiment --json`` exits 0 and lists the manifest."""
    paper = tmp_path / "demo-paper"
    paper.mkdir()
    bootstrap = _run_scaffold(str(paper), "--kind", "paper")
    assert bootstrap.returncode == 0, bootstrap.stderr

    experiment = _run_scaffold(
        str(paper),
        "--kind",
        "experiment",
        "--name",
        "baseline",
        "--json",
    )

    assert experiment.returncode == 0, experiment.stderr
    payload = json.loads(experiment.stdout)
    files = payload.get("files", [])
    # The manifest ships under its template-owned name, ``experiment.yaml``.
    assert any(
        "manifest" in str(f).lower() or str(f).endswith("experiment.yaml")
        for f in files
    ), payload


def _check_json(project: Path) -> dict[str, object]:
    # Run ``axm-init check --json`` on *project* and parse the report.
    completed = subprocess.run(
        ["uv", "run", "axm-init", "check", str(project), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    report: dict[str, object] = json.loads(completed.stdout)
    return report


def test_scaffolded_experiment_is_checked_as_an_experiment(tmp_path: Path) -> None:
    # AC4: scaffold via the public tool, then check -> experiment, no failure.
    paper = tmp_path / "tool-paper"
    paper.mkdir()
    tool = InitScaffoldTool()
    bootstrap = tool.execute(
        path=str(paper),
        kind="paper",
        name="tool-paper",
        **SCAFFOLD_IDENTITY,
    )
    assert bootstrap.success, bootstrap.error
    made = tool.execute(
        path=str(paper),
        kind="experiment",
        name="baseline",
        **SCAFFOLD_IDENTITY,
    )
    assert made.success, made.error
    assert isinstance(made.data, dict)

    report = _check_json(Path(str(made.data["path"])))

    assert report["context"] == "experiment"
    assert report["failures"] == []


def test_cli_scaffold_then_check_reports_no_packaging_failure(tmp_path: Path) -> None:
    # AC5: CLI scaffold + CLI check -> experiment context, no packaging id fails.
    paper = tmp_path / "cli-paper"
    paper.mkdir()
    bootstrap = _run_scaffold(str(paper), "--kind", "paper")
    assert bootstrap.returncode == 0, bootstrap.stderr

    experiment = _run_scaffold(
        str(paper),
        "--kind",
        "experiment",
        "--name",
        "baseline",
        "--json",
    )
    assert experiment.returncode == 0, experiment.stderr
    payload = json.loads(experiment.stdout)

    report = _check_json(Path(str(payload["path"])))

    assert report["context"] == "experiment"
    failures = report["failures"]
    assert isinstance(failures, list)
    failed = {str(f["name"]) for f in failures}
    assert PACKAGING_CHECK_IDS.isdisjoint(failed), sorted(failed)


def test_scaffolded_paper_keeps_the_research_check_green(tmp_path: Path) -> None:
    """AC5: a CLI-scaffolded paper ships RESEARCH.md and checks green on it."""
    paper = tmp_path / "research-paper"
    paper.mkdir()
    bootstrap = _run_scaffold(str(paper), "--kind", "paper")
    assert bootstrap.returncode == 0, bootstrap.stderr

    assert (paper / RESEARCH_FILENAME).is_file(), sorted(
        p.name for p in paper.iterdir()
    )

    report = _check_json(paper)

    failures = report["failures"]
    assert isinstance(failures, list)
    failed = {str(f["name"]) for f in failures}
    assert RESEARCH_CHECK_ID not in failed, sorted(failed)
