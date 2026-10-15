"""Public shared-unit scaffold proofs, with real filesystem and static checks."""

from __future__ import annotations

import ast
import copy
import tomllib
from pathlib import Path

import pytest
from tomlkit import dumps, parse, table

from axm_init.checks.protocols import (
    check_protocol_ticket,
    protocol_collisions,
    protocol_inventory,
)
from axm_init.tools.check import InitCheckTool
from axm_init.tools.scaffold import InitScaffoldTool

IDENTITY = {"org": "test-org", "author": "Test Author", "email": "test@example.com"}
SHARED: dict[str, object] = {
    "contracts": [{"name": "run_context"}],
    "ticket": {
        "ticket_type": "ml.run",
        "input_contract": "run_context",
        "entry_action": "exec",
    },
}
ACTIONS: list[dict[str, object]] = [
    {"action": action, "contracts": [], "nodes": [], "unit_ticket": "ml.run"}
    for action in ("exec", "inspect")
]


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "protocols-ml"\nversion = "0.1.0"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/protocols_ml"]\n'
        '[tool.axm-init.protocols]\nschema_version = 1\ndomain = "ml"\n',
        encoding="utf-8",
    )
    return tmp_path


def _snapshot(project: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(project)): path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


def _apply(project: Path, *, preview: bool = False) -> None:
    result = InitScaffoldTool().execute(
        path=str(project),
        kind="protocol_unit",
        profile="protocols",
        domain="ml",
        unit="run",
        protocols=ACTIONS,
        unit_declaration=SHARED,
        preview=preview,
        **IDENTITY,
    )
    assert result.success, result.error


def test_init_scaffold_shared_ticket_preview_apply_reapply(project: Path) -> None:
    before = _snapshot(project)
    _apply(project, preview=True)
    assert _snapshot(project) == before
    _apply(project)
    root = project / "src/protocols_ml/run"
    assert (root / "ticket.py").is_file()
    assert (root / "contracts/run_context.py").is_file()
    assert not (root / "exec/ticket.py").exists()
    assert not (root / "inspect/ticket.py").exists()
    for action in ("exec", "inspect"):
        tree = ast.parse((root / action / "protocol.py").read_text())
        imports = {
            node.module for node in tree.body if isinstance(node, ast.ImportFrom)
        }
        assert "protocols_ml.run.ticket" in imports
        assert "protocols_ml.run.contracts.run_context" in imports
    metadata = tomllib.loads((project / "pyproject.toml").read_text())
    profile = metadata["tool"]["axm-init"]["protocols"]
    assert profile["schema_version"] == 2
    unit = profile["units"][0]
    assert unit["ticket_type"] == "ml.run"
    assert unit["entry_action"] == "exec"
    assert [action["unit_ticket"] for action in unit["protocols"]] == [
        "ml.run",
        "ml.run",
    ]
    check = InitCheckTool().execute(path=str(project), category="protocols")
    assert check.success, check.data
    assert protocol_collisions([("protocols-ml", protocol_inventory(project))]) == []
    before = _snapshot(project)
    _apply(project)
    assert _snapshot(project) == before


def test_init_scaffold_shared_ticket_preserves_user_context_and_action(
    project: Path,
) -> None:
    _apply(project)
    root = project / "src/protocols_ml/run"
    context = root / "contracts/run_context.py"
    context.write_text(
        "from pydantic import BaseModel\nclass RunContext(BaseModel):\n    path: str\n"
    )
    action = root / "inspect/protocol.py"
    action.write_text("# implemented user action\n")
    before = _snapshot(project)
    _apply(project)
    assert _snapshot(project) == before


@pytest.mark.parametrize(
    "change", ["ticket", "context", "entry", "cross_unit", "unknown", "both"]
)
def test_init_scaffold_shared_ticket_conflicts_are_preflight(
    project: Path, change: str
) -> None:
    _apply(project)
    supplied: dict[str, object] | None = copy.deepcopy(SHARED)
    actions = copy.deepcopy(ACTIONS)
    unit = "run"
    if change == "ticket":
        supplied["ticket"] = {
            "ticket_type": "ml.other",
            "input_contract": "run_context",
            "entry_action": "exec",
        }
    elif change == "context":
        supplied["contracts"] = [{"name": "other"}]
        supplied["ticket"] = {
            "ticket_type": "ml.run",
            "input_contract": "other",
            "entry_action": "exec",
        }
    elif change == "entry":
        supplied["ticket"] = {
            "ticket_type": "ml.run",
            "input_contract": "run_context",
            "entry_action": "inspect",
        }
    elif change == "cross_unit":
        unit = "study"
        supplied = None
    elif change == "unknown":
        actions[0]["unit_ticket"] = "ml.unknown"
    elif change == "both":
        actions[0]["contracts"] = [{"name": "local"}]
        actions[0]["ticket"] = {"ticket_type": "ml.local", "input_contract": "local"}
    before = _snapshot(project)
    result = InitScaffoldTool().execute(
        path=str(project),
        kind="protocol_unit",
        profile="protocols",
        domain="ml",
        unit=unit,
        protocols=actions,
        unit_declaration=supplied,
        **IDENTITY,
    )
    assert not result.success
    assert _snapshot(project) == before


@pytest.mark.parametrize("field,value", [("domain", "other"), ("unit", "study")])
def test_init_scaffold_shared_namespace_conflict_is_preflight(
    project: Path, field: str, value: str
) -> None:
    supplied = copy.deepcopy(SHARED)
    supplied[field] = value
    before = _snapshot(project)
    result = InitScaffoldTool().execute(
        path=str(project),
        kind="protocol_unit",
        profile="protocols",
        domain="ml",
        unit="run",
        protocols=ACTIONS,
        unit_declaration=supplied,
        **IDENTITY,
    )
    assert not result.success
    assert _snapshot(project) == before


def test_init_scaffold_unowned_shared_ticket_is_never_overwritten(
    project: Path,
) -> None:
    ticket = project / "src/protocols_ml/run/ticket.py"
    ticket.parent.mkdir(parents=True)
    ticket.write_text("# user's preexisting ticket\n")
    before = _snapshot(project)
    result = InitScaffoldTool().execute(
        path=str(project),
        kind="protocol_unit",
        profile="protocols",
        domain="ml",
        unit="run",
        protocols=ACTIONS,
        unit_declaration=SHARED,
        **IDENTITY,
    )
    assert not result.success
    assert _snapshot(project) == before


def test_init_scaffold_existing_shared_reference_needs_no_redeclaration(
    project: Path,
) -> None:
    _apply(project)
    result = InitScaffoldTool().execute(
        path=str(project),
        kind="protocol",
        profile="protocols",
        domain="ml",
        unit="run",
        protocols=[
            {"action": "export", "contracts": [], "nodes": [], "unit_ticket": "ml.run"}
        ],
        **IDENTITY,
    )
    assert result.success, result.error
    assert (project / "src/protocols_ml/run/export/protocol.py").is_file()
    check = InitCheckTool().execute(path=str(project), category="protocols")
    assert check.success, check.data


def test_init_scaffold_old_action_keeps_profile_version_and_ticket(
    project: Path,
) -> None:
    _apply(project)
    legacy = [
        {
            "action": "legacy",
            "contracts": [{"name": "old"}],
            "nodes": [],
            "ticket": {"ticket_type": "ml.legacy", "input_contract": "old"},
        }
    ]
    for _ in range(2):
        result = InitScaffoldTool().execute(
            path=str(project),
            kind="protocol",
            profile="protocols",
            domain="ml",
            unit="run",
            protocols=legacy,
            **IDENTITY,
        )
        assert result.success, result.error
    metadata = tomllib.loads((project / "pyproject.toml").read_text())
    assert metadata["tool"]["axm-init"]["protocols"]["schema_version"] == 2
    assert (project / "src/protocols_ml/run/legacy/ticket.py").is_file()
    check = InitCheckTool().execute(path=str(project), category="protocols")
    assert check.success, check.data


@pytest.fixture()
def ready_project(project: Path) -> Path:
    _apply(project)
    root = project / "src/protocols_ml/run"
    (root / "contracts/run_context.py").write_text(
        "from pydantic import BaseModel\n"
        "__all__ = ['RunContext']\n"
        "class RunContext(BaseModel):\n    destination: str\n"
    )
    for action in ("exec", "inspect"):
        (root / action / "protocol.py").write_text(
            "from axm_tribunal import protocol\n"
            "from protocols_ml.run.contracts.run_context import RunContext\n"
            "from protocols_ml.run.ticket import get_ticket_type\n"
            "__all__ = ['build_protocol', 'RunContext', 'get_ticket_type']\n"
            "UNIT_TICKET = 'ml.run'\n"
            "def build_protocol():\n"
            f"    return protocol('ml.run.{action}', phases=[])\n"
        )
    path = project / "pyproject.toml"
    document = parse(path.read_text())
    for action in document["tool"]["axm-init"]["protocols"]["units"][0]["protocols"]:
        action["state"] = "ready"
    entries = table()
    entries["axm.tribunal.graphs"] = {
        f"ml.run.{action}": f"protocols_ml.run.{action}.protocol:build_protocol"
        for action in ("exec", "inspect")
    }
    entries["axm.tribunal.ticket_types"] = {
        "ml.run": "protocols_ml.run.ticket:get_ticket_type"
    }
    document["project"]["entry-points"] = entries
    path.write_text(dumps(document))
    return project


def test_check_shared_ticket_ready_reapply(ready_project: Path) -> None:
    result = InitCheckTool().execute(path=str(ready_project), category="protocols")
    assert result.success, result.data
    before = _snapshot(ready_project)
    _apply(ready_project)
    assert _snapshot(ready_project) == before
    records = protocol_inventory(ready_project)
    claims = {
        claim
        for record in records
        for claim in record.claims
        if claim[0] == "axm.tribunal.ticket_types"
    }
    assert len(claims) == 1
    assert next(iter(claims))[1] == "ml.run"


@pytest.mark.parametrize(
    "change",
    [
        "wrong_group",
        "wrong_factory",
        "alias",
        "legacy_alias",
        "duplicate",
        "missing_graph",
    ],
)
def test_check_shared_ticket_registration(ready_project: Path, change: str) -> None:
    path = ready_project / "pyproject.toml"
    document = parse(path.read_text())
    entries = document["project"]["entry-points"]
    target = "protocols_ml.run.ticket:get_ticket_type"
    if change == "wrong_group":
        del entries["axm.tribunal.ticket_types"]
        entries["axm.ticket_types"] = {"ml.run": target}
    elif change == "wrong_factory":
        entries["axm.tribunal.ticket_types"]["ml.run"] = (
            "protocols_ml.run.exec.ticket:get_ticket_type"
        )
    elif change == "alias":
        entries["axm.tribunal.ticket_types"]["ml.other"] = target
    elif change == "legacy_alias":
        entries["axm.ticket_types"] = {"ml.other": target}
    elif change == "duplicate":
        entries["axm.ticket_types"] = {"ml.run": target}
    elif change == "missing_graph":
        del entries["axm.tribunal.graphs"]["ml.run.exec"]
    path.write_text(dumps(document))
    result = InitCheckTool().execute(path=str(ready_project), category="protocols")
    assert not result.success
    assert not check_protocol_ticket(ready_project).passed


@pytest.mark.parametrize(
    "change",
    [
        "wrong_context",
        "wrong_graph",
        "wrong_factory",
        "missing_context",
        "bad_ref",
        "schema1",
    ],
)
def test_check_shared_ticket_resources(project: Path, change: str) -> None:
    _apply(project)
    root = project / "src/protocols_ml/run"
    if change in ("wrong_context", "wrong_graph", "wrong_factory"):
        path = root / "ticket.py"
        text = path.read_text()
        if change == "wrong_context":
            text = text.replace("context_model=RunContext", "context_model=str")
        elif change == "wrong_graph":
            text = text.replace(
                "GRAPH_NAME = 'ml.run.exec'", "GRAPH_NAME = 'ml.run.inspect'"
            )
        else:
            text = text.replace("return TicketTypeDef(", "return dict(")
        path.write_text(text)
    elif change == "missing_context":
        (root / "contracts/run_context.py").unlink()
    else:
        path = project / "pyproject.toml"
        document = parse(path.read_text())
        profile = document["tool"]["axm-init"]["protocols"]
        if change == "bad_ref":
            profile["units"][0]["protocols"][0]["unit_ticket"] = "ml.study"
        else:
            profile["schema_version"] = 1
        path.write_text(dumps(document))
    result = InitCheckTool().execute(path=str(project), category="protocols")
    assert not result.success


def test_check_shared_ticket_refuses_publication_while_entry_is_draft(
    project: Path,
) -> None:
    _apply(project)
    metadata = project / "pyproject.toml"
    with metadata.open("a") as stream:
        stream.write(
            '\n[project.entry-points."axm.tribunal.ticket_types"]\n'
            '"ml.run" = "protocols_ml.run.ticket:get_ticket_type"\n'
        )
    check = check_protocol_ticket(project)
    assert not check.passed
    assert any("entry graph ready" in finding for finding in check.details)
