"""E2E tests for ``axm init_scaffold`` (black box, subprocess)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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
        [str(Path(sys.executable).with_name("axm")), "init_scaffold", *tool_args],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.e2e
def test_experiment_cli_refuses_retired_layout(tmp_path: Path) -> None:
    proc = _run([str(tmp_path), "--kind", "experiment", "--json", *IDENTITY])
    assert proc.returncode != 0
    assert "experiment_scaffold" in proc.stdout + proc.stderr
    assert "axm-lab" in proc.stdout + proc.stderr
    assert list(tmp_path.iterdir()) == []


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
    # The target must already own the profile: a unit or protocol request
    # refuses a package declaring no `[tool.axm-init.protocols].domain` rather
    # than registering one for it (ownership is a package-creation decision).
    pyproject.write_text(
        '[project]\nname = "protocols-dev"\nversion = "0.1.0"\n\n'
        '[tool.axm-init.protocols]\nschema_version = 1\ndomain = "dev"\n',
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


@pytest.mark.e2e
def test_learning_scaffold_cli_creates_learning_configs(tmp_path: Path) -> None:
    """AC7: the learning CLI exits zero and writes both learning configs."""
    proc = _run(
        [
            str(tmp_path),
            "--kind",
            "learning",
            "--name",
            "learning-cli",
            *IDENTITY,
        ]
    )

    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "training.toml").is_file()
    assert (tmp_path / "study.toml").is_file()
