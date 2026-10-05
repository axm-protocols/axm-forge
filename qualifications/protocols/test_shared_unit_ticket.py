"""Explicit cross-environment proof; not collected by standard Forge testpaths."""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

from axm_init.tools.scaffold import InitScaffoldTool


def test_generated_ticket_factory_is_real_protocols_core(tmp_path: Path) -> None:
    declared = os.environ.get("AXM_PROTOCOLS_PYTHON")
    if declared is None:
        declared = tomllib.loads(Path(__file__).with_name("runtime.toml").read_text())[
            "python"
        ]
    interpreter = Path(declared).absolute()
    assert interpreter.is_file()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "protocols-ml"\nversion = "0.1.0"\n'
        '[tool.axm-init.protocols]\nschema_version = 1\ndomain = "ml"\n'
    )
    result = InitScaffoldTool().execute(
        path=str(tmp_path),
        kind="protocol_unit",
        profile="protocols",
        domain="ml",
        unit="run",
        org="proof-org",
        author="Proof",
        email="proof@example.com",
        unit_declaration={
            "contracts": [{"name": "run_context"}],
            "ticket": {
                "ticket_type": "ml.run",
                "input_contract": "run_context",
                "entry_action": "exec",
            },
        },
        protocols=[
            {"action": action, "contracts": [], "nodes": [], "unit_ticket": "ml.run"}
            for action in ("exec", "inspect")
        ],
    )
    assert result.success, result.error
    script = (
        "import json, sys\n"
        "from importlib.metadata import version\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from protocols_core import TicketTypeDef\n"
        "from protocols_ml.run.ticket import get_ticket_type\n"
        "from protocols_ml.run.contracts.run_context import RunContext\n"
        "from protocols_ml.run.exec.protocol import get_ticket_type as entry_factory\n"
        "from protocols_ml.run.inspect.protocol import get_ticket_type as other_factory\n"
        "definition = get_ticket_type()\n"
        "assert type(definition) is TicketTypeDef\n"
        "assert definition.name == 'ml.run'\n"
        "assert definition.context_model is RunContext\n"
        "assert definition.graph == 'ml.run.exec'\n"
        "assert entry_factory is get_ticket_type is other_factory\n"
        "print(json.dumps({'package_version': version('protocols-core'), "
        "'type_module': TicketTypeDef.__module__, 'name': definition.name, "
        "'entry_graph': definition.graph}))\n"
    )
    completed = subprocess.run(
        [str(interpreter), "-c", script, str(tmp_path / "src")],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"name": "ml.run"' in completed.stdout
    assert '"entry_graph": "ml.run.exec"' in completed.stdout
