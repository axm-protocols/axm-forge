"""E2E tests for the ``axm-init scaffold`` CLI (black box, subprocess)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

IDENTITY = [
    "--org",
    "test-org",
    "--author",
    "Test Author",
    "--email",
    "test@example.com",
]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    # Invoke the installed ``axm-init`` console script.
    return subprocess.run(
        ["axm-init", *args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.e2e
class TestScaffoldExperimentCli:
    # ``axm-init scaffold --kind experiment --json`` reports the manifest.

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
