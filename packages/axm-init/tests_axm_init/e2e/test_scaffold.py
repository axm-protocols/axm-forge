"""E2E tests for ``axm init_scaffold`` (black box, subprocess)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from axm_init.checks.experiment import (
    check_experiment_files,
    check_experiment_structure,
)

MANIFEST = "manifest.yaml"
CONTRACT_VERSION = "1.1.0"

IDENTITY = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@example.com",
]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Invoke the generated AXMTool command through the shared dispatcher.
    tool_args = args[1:] if args and args[0] == "scaffold" else args
    tool_args = ["--json-output" if arg == "--json" else arg for arg in tool_args]
    return subprocess.run(
        ["uv", "run", "axm", "init_scaffold", *tool_args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.e2e
class TestScaffoldExperimentCli:
    # ``axm init_scaffold --kind experiment --json-output`` reports the manifest.

    def test_experiment_json_lists_manifest_in_the_produced_tree(
        self, tmp_path: Path
    ) -> None:
        """AC3: exit 0 and a payload listing manifest.yaml, not experiment.yaml.

        The listed paths name the files rendered into the experiment directory
        the same payload reports, so each one must resolve there.
        """
        paper = _run(["scaffold", str(tmp_path), "--kind", "paper", *IDENTITY])
        assert paper.returncode == 0, paper.stderr

        proc = _run(
            [
                "scaffold",
                str(tmp_path),
                "--kind",
                "experiment",
                "--json",
                *IDENTITY,
            ]
        )
        assert proc.returncode == 0, proc.stderr

        payload = json.loads(proc.stdout)
        files = [str(f) for f in payload["files"]]
        experiment_dir = Path(str(payload["path"]))
        assert any(f.endswith("manifest.yaml") for f in files), files
        assert not any(f.endswith("experiment.yaml") for f in files), files
        unresolved = [f for f in files if not (experiment_dir / f).is_file()]
        assert unresolved == []

    def test_experiment_cli_renders_figures_yaml_and_analysis_note(
        self, tmp_path: Path
    ) -> None:
        """AC4: the CLI render writes figures.yaml + analysis.md, no FIGURES.md.

        The same four facts as the integration render, observed black box
        through the scaffold subprocess and the tree its payload reports.
        """
        paper = _run(["scaffold", str(tmp_path), "--kind", "paper", *IDENTITY])
        assert paper.returncode == 0, paper.stderr

        proc = _run(
            [
                "scaffold",
                str(tmp_path),
                "--kind",
                "experiment",
                "--json",
                *IDENTITY,
            ]
        )
        assert proc.returncode == 0, proc.stderr

        payload = json.loads(proc.stdout)
        experiment_dir = Path(str(payload["path"]))
        rendered = sorted(
            p.relative_to(experiment_dir).as_posix()
            for p in experiment_dir.rglob("*")
            if p.is_file()
        )
        assert (experiment_dir / "figures" / "figures.yaml").is_file(), rendered
        assert [f for f in rendered if f.endswith("FIGURES.md")] == []
        assert (experiment_dir / "analysis" / "analysis.md").is_file(), rendered
        assert [f for f in rendered if f.startswith("analysis/metrics.")] == []

    def test_experiment_manifest_declares_supports_and_the_bumped_version(
        self, tmp_path: Path
    ) -> None:
        """AC3: the scaffolded manifest holds contract_version 1.1.0 + supports.

        Observed black box on the very folder the CLI produced, on which the
        package's own experiment form checks must stay green.
        """
        paper = _run(["scaffold", str(tmp_path), "--kind", "paper", *IDENTITY])
        assert paper.returncode == 0, paper.stderr

        proc = _run(
            [
                "scaffold",
                str(tmp_path),
                "--kind",
                "experiment",
                "--json",
                *IDENTITY,
            ]
        )
        assert proc.returncode == 0, proc.stderr

        payload = json.loads(proc.stdout)
        experiment_dir = Path(str(payload["path"]))
        raw = (experiment_dir / MANIFEST).read_text(encoding="utf-8")
        document = yaml.safe_load(raw)
        assert isinstance(document, dict), raw
        assert document["contract_version"] == CONTRACT_VERSION, document
        assert "supports" in document, sorted(document)
        assert isinstance(document["supports"], list), document["supports"]

        structure = check_experiment_structure(experiment_dir)
        files = check_experiment_files(experiment_dir)
        assert structure.passed, structure.message
        assert files.passed, files.message


@pytest.mark.e2e
def test_protocol_preview_cli_matches_axmtool_structured_payload(
    tmp_path: Path,
) -> None:
    """AC3: CLI and direct AXMTool return the same structured preview payload."""
    from axm_init.tools.scaffold import InitScaffoldTool

    declaration: dict[str, object] = {
        "domain": "dev",
        "unit": "work",
        "action": "create",
        "contracts": [{"name": "brief"}],
        "nodes": [{"name": "author", "contract": "brief"}],
    }
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "protocols-dev"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    direct = InitScaffoldTool().execute(
        path=str(tmp_path),
        profile="protocols",
        domain="dev",
        unit="work",
        protocols=[declaration],
        preview=True,
        org="test-org",
        author="Test Author",
        email="test@example.com",
    )
    assert direct.success, direct.error
    assert direct.data is not None

    proc = _run(
        [
            str(tmp_path),
            "--profile",
            "protocols",
            "--domain",
            "dev",
            "--unit",
            "work",
            "--protocols",
            json.dumps([declaration]),
            "--preview",
            "--json",
            *IDENTITY,
        ]
    )
    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    keys = {
        "profile",
        "mode",
        "root",
        "preview",
        "created",
        "updated",
        "unchanged",
        "conflicts",
        "protocols",
    }
    assert {key: cli_payload[key] for key in keys} == {
        key: direct.data[key] for key in keys
    }
