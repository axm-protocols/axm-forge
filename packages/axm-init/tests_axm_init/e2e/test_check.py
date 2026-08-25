"""E2E test: ``axm-init check`` surfaces wheel-doc-shipping failures (AXM-1715)."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_check_command_exits_nonzero_on_orphan_doc(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "pkg"

            [tool.axm-init.wheel-doc]
            files = ["docs/x.md"]

            [tool.hatch.build.targets.wheel]
            packages = ["src/pkg"]
            """
        ).lstrip()
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_text("# x\n")

    proc = subprocess.run(
        ["uv", "run", "axm-init", "check", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "pyproject.pyproject_wheel_doc_shipping" in combined
    assert "x.md" in combined


def _run_check(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke `axm-init check` with *args* and capture the outcome."""
    return subprocess.run(
        ["uv", "run", "axm-init", "check", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_workspace_category_on_standalone_prints_na(tmp_path: Path) -> None:
    """AC1/AC2: `check --category workspace` on a standalone project prints an
    N/A line (not 0/100 Grade F) and exits 0."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    proc = _run_check(str(tmp_path), "--category", "workspace")

    combined = proc.stdout + proc.stderr
    assert "not applicable" in combined or "N/A" in combined
    assert "Score: 0/100" not in combined
    assert proc.returncode == 0


def test_check_inapplicable_category_exit_code_is_zero(tmp_path: Path) -> None:
    """AC2: an inapplicable category returns exit code exactly 0."""
    proc = _run_check(str(tmp_path), "--category", "workspace")

    assert proc.returncode == 0


def test_check_failing_applicable_category_exits_one(tmp_path: Path) -> None:
    """AC3: an applicable category scoring a real 0 exits 1 with 0/100 Grade F."""
    proc = _run_check(str(tmp_path), "--category", "ci")

    combined = proc.stdout + proc.stderr
    assert "0/100" in combined
    assert "Grade F" in combined
    assert proc.returncode == 1


def _member_skip_ids() -> frozenset[str]:
    """The member entry of the skip table the check engine must expose."""
    from axm_init.checks._workspace import ProjectContext
    from axm_init.core import checker

    table = getattr(checker, "SKIP_BY_CONTEXT", None)
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return frozenset(table[ProjectContext.MEMBER])


def _collect_names(node: object, acc: set[str]) -> None:
    """Collect every name string reachable in a parsed JSON payload."""
    if isinstance(node, dict):
        name = node.get("name")
        if isinstance(name, str):
            acc.add(name)
        for value in node.values():
            _collect_names(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_names(value, acc)


def test_check_json_report_omits_member_skipped_ids(tmp_path: Path) -> None:
    """AC5: the CLI report on a member names no id of the member skip table."""
    from axm_init.core.checker import ALL_CHECKS, get_check_name

    skipped = _member_skip_ids()

    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    (ws_root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = ws_root / "packages" / "foo"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "foo"\n')

    proc = _run_check(str(member), "--json")
    payload = json.loads(proc.stdout)
    names: set[str] = set()
    _collect_names(payload, names)

    discovered = {get_check_name(fn) for fns in ALL_CHECKS.values() for fn in fns}

    assert names & skipped == set()
    assert names & (discovered - skipped)


def _collect_contexts(node: object, acc: set[str]) -> None:
    """Collect every ``context`` string reachable in a parsed JSON payload."""
    if isinstance(node, dict):
        context = node.get("context")
        if isinstance(context, str):
            acc.add(context)
        for value in node.values():
            _collect_contexts(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_contexts(value, acc)


def _paper_project(root: Path) -> Path:
    """Hand-build a paper: axm-lab marker, paper tree, plan with front-matter."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-x"\nversion = "0.1.0"\n\n'
        '[tool.axm-lab]\nslug = "paper-x"\n'
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper X\n")
    (root / "plan.md").write_text("---\ntitle: Paper X\nstatus: draft\n---\n\n# Plan\n")
    return root


def test_check_on_a_paper_reports_no_packaging_failure(tmp_path: Path) -> None:
    """AC4: the CLI report on a paper holds no packaging failure.

    Deliberately makes no claim about the exit code: a paper may still fail a
    paper-specific check, and the exit code encodes overall grade.
    """
    project = _paper_project(tmp_path / "paper-x")

    proc = _run_check(str(project), "--json")
    payload = json.loads(proc.stdout)

    failures = payload.get("failures", [])
    names = {
        entry["name"]
        for entry in failures
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    packaging = sorted(name for name in names if not name.startswith("paper."))

    assert packaging == []


def test_check_json_report_exposes_the_paper_context(tmp_path: Path) -> None:
    """AC2: the CLI report on an axm-lab project exposes the paper context."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "paper-x"\n\n[tool.axm-lab]\nslug = "paper-x"\n'
    )

    proc = _run_check(str(tmp_path), "--json")
    payload = json.loads(proc.stdout)
    contexts: set[str] = set()
    _collect_contexts(payload, contexts)

    assert "paper" in contexts


def test_check_json_report_names_the_canonical_plan_document(tmp_path: Path) -> None:
    """AC3: on a paper carrying no plan file, the JSON report names PLAN.md
    and never the lowercase form."""
    root = tmp_path / "paper-z"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-z"\n\n[tool.axm-lab]\nslug = "paper-z"\n'
    )

    proc = _run_check(str(root), "--json")
    payload = json.loads(proc.stdout)
    names: set[str] = set()
    _collect_names(payload, names)
    blob = json.dumps(payload)

    assert proc.returncode != 0
    assert "paper.plan_present" in names
    assert "PLAN.md" in blob
    assert "plan.md" not in blob


def test_check_json_report_names_the_missing_provenance_document(
    tmp_path: Path,
) -> None:
    # AC1: on a paper carrying no provenance document, the CLI exits non-zero
    # and its paper-structure failure entry names PIPELINE.md.
    root = tmp_path / "paper-p"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-p"\n\n[tool.axm-lab]\nslug = "paper-p"\n'
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper P\n")
    (root / "PLAN.md").write_text("---\ntitle: Paper P\nstatus: draft\n---\n\n# Plan\n")

    proc = _run_check(str(root), "--json")
    payload = json.loads(proc.stdout)
    failures = payload.get("failures", [])
    structure = [
        entry
        for entry in failures
        if isinstance(entry, dict) and entry.get("name") == "paper.paper_structure"
    ]

    assert proc.returncode != 0
    assert structure, payload
    assert "PIPELINE.md" in json.dumps(structure)


def test_check_json_report_exposes_the_experiment_context(tmp_path: Path) -> None:
    """AC2: the CLI report on an experiment folder exposes the experiment context."""
    root = tmp_path / "01-demo"
    root.mkdir()
    (root / "manifest.yaml").write_text("contract_version: 1\nid: 01-demo\n")
    (root / "README.md").write_text("# 01-demo\n")
    for name in ("inputs", "scripts", "outputs", "logs", "figures"):
        (root / name).mkdir()

    proc = _run_check(str(root), "--json")
    payload = json.loads(proc.stdout)
    contexts: set[str] = set()
    _collect_contexts(payload, contexts)

    assert "experiment" in contexts


def test_check_json_report_flags_the_missing_research_document(tmp_path: Path) -> None:
    # AC2: on a paper carrying no research protocol document, the JSON report
    # holds a failed paper.research_present entry naming RESEARCH.md.
    root = tmp_path / "paper-r"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "paper-r"\n\n[tool.axm-lab]\nslug = "paper-r"\n'
    )
    (root / "paper").mkdir()
    (root / "experiments").mkdir()
    (root / "README.md").write_text("# Paper R\n")
    (root / "PIPELINE.md").write_text("# Pipeline\n")
    (root / "PLAN.md").write_text("---\ntitle: Paper R\n---\n\n# Plan\n")

    proc = _run_check(str(root), "--json")
    payload = json.loads(proc.stdout)
    failures = payload.get("failures", [])
    research = [
        entry
        for entry in failures
        if isinstance(entry, dict) and entry.get("name") == "paper.research_present"
    ]

    assert research, payload
    assert "RESEARCH.md" in json.dumps(research)
