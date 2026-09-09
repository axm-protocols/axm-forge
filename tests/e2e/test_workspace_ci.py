"""Exercise the workspace selector and badge aggregation through their CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github/scripts/workspace_ci.py"
pytestmark = pytest.mark.e2e


def _workspace(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*", "libs/*"]\n'
        'exclude = ["packages/ignored"]\n'
    )
    for directory, name, dependencies in [
        ("packages/sdk", "demo-core", []),
        ("packages/feature", "demo-feature", ["demo_core>=1"]),
        ("libs/client", "demo-client", ["demo-feature[extra]"]),
        ("packages/ignored", "ignored", []),
    ]:
        member = root / directory
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.0.0"\n'
            f"dependencies = {json.dumps(dependencies)}\n"
            '[tool.pytest.ini_options]\ntestpaths = ["checks"]\n'
        )


def _run(
    root: Path, changed: list[str] | None = None, event: dict[str, object] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "packages/axm-ingot/src")
    env.pop("GITHUB_EVENT_PATH", None)
    env.pop("GITHUB_OUTPUT", None)
    args = [sys.executable, str(SCRIPT), "--root", str(root)]
    if changed is not None:
        fixture = root / "changes.json"
        fixture.write_text(json.dumps(changed))
        args += ["--changed", str(fixture)]
    if event is not None:
        fixture = root / "event.json"
        fixture.write_text(json.dumps(event))
        args += ["--event", str(fixture)]
    return subprocess.run(args, env=env, text=True, capture_output=True, check=False)


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ([], []),
        (["README.md"], []),
        (["packages/sdk/src/a.py"], ["demo-client", "demo-core", "demo-feature"]),
        (["packages/feature/README.md"], ["demo-client", "demo-feature"]),
        (["libs/client/src/a.py"], ["demo-client"]),
        (["uv.lock"], ["demo-client", "demo-core", "demo-feature"]),
        (
            [".github/actions/workspace-matrix/action.yml"],
            ["demo-client", "demo-core", "demo-feature"],
        ),
        (
            ["packages/deleted/pyproject.toml"],
            ["demo-client", "demo-core", "demo-feature"],
        ),
        (
            ["packages/feature/src/templates/sample.txt"],
            ["demo-client", "demo-core", "demo-feature"],
        ),
    ],
)
def test_changed_members_and_dependants(
    tmp_path: Path, changes: list[str], expected: list[str]
) -> None:
    _workspace(tmp_path)
    result = _run(tmp_path, changes)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [m["name"] for m in payload["packages"]] == expected
    assert payload["any"] == bool(expected)
    assert {m["name"]: m["path"] for m in payload["all"]} == {
        "demo-core": "packages/sdk",
        "demo-feature": "packages/feature",
        "demo-client": "libs/client",
    }
    assert all(m["tests"] == ["checks"] for m in payload["all"])


def test_new_member_is_discovered_without_workflow_edits(tmp_path: Path) -> None:
    _workspace(tmp_path)
    new = tmp_path / "libs/new-dir"
    new.mkdir()
    (new / "pyproject.toml").write_text('[project]\nname="new-distribution"\n')
    result = _run(tmp_path, ["libs/new-dir/pyproject.toml"])
    assert result.returncode == 0, result.stderr
    assert [m["name"] for m in json.loads(result.stdout)["packages"]] == [
        "new-distribution"
    ]


@pytest.mark.parametrize("base", ["0" * 40, "f" * 40])
def test_missing_history_runs_every_member(tmp_path: Path, base: str) -> None:
    _workspace(tmp_path)
    result = _run(tmp_path, event={"before": base})
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["packages"] == payload["all"]
    assert len(payload["packages"]) == 3


def test_duplicate_distribution_names_fail_closed(tmp_path: Path) -> None:
    _workspace(tmp_path)
    (tmp_path / "libs/client/pyproject.toml").write_text(
        '[project]\nname="demo_core"\n'
    )
    result = _run(tmp_path)
    assert result.returncode != 0
    assert "Duplicate project name" in result.stderr


def test_git_push_diff_and_pr_merge_base(tmp_path: Path) -> None:
    _workspace(tmp_path)

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", "user.name=CI", "-c", "user.email=ci@example.test", *args],
            cwd=tmp_path,
            text=True,
        ).strip()

    git("init")
    git("add", ".")
    git("commit", "-m", "initial")
    base = git("rev-parse", "HEAD")
    (tmp_path / "libs/client/new.txt").write_text("changed")
    git("add", ".")
    git("commit", "-m", "client")
    for event in [{"before": base}, {"pull_request": {"base": {"sha": base}}}]:
        result = _run(tmp_path, event=event)
        assert result.returncode == 0, result.stderr
        assert [m["name"] for m in json.loads(result.stdout)["packages"]] == [
            "demo-client"
        ]


def test_aggregation_uses_current_inventory_and_counts_failed_coverage(
    tmp_path: Path,
) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/axm-quality.yml").read_text())
    step = next(s for s in workflow["jobs"]["publish"]["steps"] if s.get("id") == "agg")
    for name, score in [("new-member", 79.9), ("other-member", 90.9), ("removed", 0)]:
        for category in ["axm-audit", "axm-init"]:
            dest = tmp_path / "_publish/reports" / category / f"{name}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({"score": score}))
    coverage = tmp_path / "_publish/reports/coverage/new-member.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(json.dumps({"totals": {"percent_covered_display": "80.0"}}))
    env = os.environ.copy()
    env.update(
        GITHUB_WORKSPACE=str(ROOT),
        GITHUB_OUTPUT=str(tmp_path / "outputs"),
        MEMBERS=json.dumps([{"name": "new-member"}, {"name": "other-member"}]),
    )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(
        (tmp_path / "_publish/reports/axm-audit/summary.json").read_text()
    )
    assert summary == {"score": 85, "coverage": 40, "members": 2}
    assert "coverage=40" in (tmp_path / "outputs").read_text()


@pytest.mark.parametrize("current", [True, False])
def test_publication_skips_superseded_snapshot(tmp_path: Path, current: bool) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/axm-quality.yml").read_text())
    step = next(
        s for s in workflow["jobs"]["publish"]["steps"] if s.get("id") == "current"
    )
    for args in [
        ["init", "-b", "main"],
        [
            "-c",
            "user.name=CI",
            "-c",
            "user.email=ci@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "initial",
        ],
        ["remote", "add", "origin", "."],
    ]:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    env = os.environ.copy()
    env.update(
        GITHUB_SHA=head if current else "0" * 40,
        GITHUB_OUTPUT=str(tmp_path / "outputs"),
    )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (
        tmp_path / "outputs"
    ).read_text().strip() == f"publish={str(current).lower()}"
