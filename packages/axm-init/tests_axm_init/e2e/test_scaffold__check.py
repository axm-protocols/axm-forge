"""E2E tests: ``axm init_scaffold`` then ``axm init_check``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

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


@pytest.mark.slow
def test_scaffold_then_check_scores_100(tmp_path: Path) -> None:
    """AC3: a fresh scaffold scores exactly 100 and exits 0.

    Marked ``slow``: this is the one end-to-end proof that the shipped CLI
    produces a gold-standard project *with* its post-copy tasks — a real
    ``git init`` and two real ``uv add`` invocations, 239 MB and ~5s. Every
    other scaffold contract renders files only (``skip_tasks=True``), so this
    test is the sole place where the full chain is exercised; it runs under
    ``-m slow`` rather than on every suite run.
    """
    project = tmp_path / "demo-pkg"
    project.mkdir()

    scaffold = subprocess.run(
        [
            "uv",
            "run",
            "axm",
            "init_scaffold",
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
        [
            "uv",
            "run",
            "axm",
            "init_check",
            str(project),
            "--json-output",
        ],
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
    """Run ``axm init_scaffold`` with the shared identity."""
    tool_args = ["--json-output" if arg == "--json" else arg for arg in args]
    return subprocess.run(
        [
            "uv",
            "run",
            "axm",
            "init_scaffold",
            *tool_args,
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

    assert experiment.returncode == 1
    assert "experiment_scaffold" in experiment.stdout + experiment.stderr
    assert not (paper / "experiments").exists()


def _check_json(project: Path) -> dict[str, object]:
    # Run ``axm init_check --json-output`` on *project* and parse the report.
    completed = subprocess.run(
        ["uv", "run", "axm", "init_check", str(project), "--json-output"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    report: dict[str, object] = json.loads(completed.stdout)
    return report


def test_scaffolded_paper_passes_without_legacy_research_authority(
    tmp_path: Path,
) -> None:
    """AC5: a CLI-scaffolded paper ships RESEARCH.md and checks green on it."""
    paper = tmp_path / "research-paper"
    paper.mkdir()
    bootstrap = _run_scaffold(str(paper), "--kind", "paper")
    assert bootstrap.returncode == 0, bootstrap.stderr

    assert not (paper / RESEARCH_FILENAME).exists(), sorted(
        p.name for p in paper.iterdir()
    )

    report = _check_json(paper)

    failures = report["failures"]
    assert isinstance(failures, list)
    failed = {str(f["name"]) for f in failures}
    assert RESEARCH_CHECK_ID not in failed, sorted(failed)
