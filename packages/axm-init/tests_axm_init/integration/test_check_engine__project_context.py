"""Split from ``test_check_engine_run_and_format.py``."""

from __future__ import annotations

from pathlib import Path

import pytest

from axm_init.checks._workspace import ProjectContext
from axm_init.core import checker
from axm_init.core.checker import ALL_CHECKS, CheckEngine, get_check_name
from axm_init.core.protocol_planner import plan_protocol_scaffold
from axm_init.models.check import CheckResult, ProjectResult
from axm_init.models.protocol_scaffold import (
    ContractDecl,
    ProtocolScaffoldDecl,
    TicketDecl,
)

__all__: list[str] = []


class TestEngineMember:
    """Member context redirects CI/tooling to workspace root."""

    def test_engine_member_redirects_ci(
        self, tmp_path: Path, gold_project__from_check_engine_run_and_format: Path
    ) -> None:
        """Member CI checks run against workspace root."""
        # Create workspace structure: tmp_path is workspace root
        ws_root = tmp_path / "workspace"
        ws_root.mkdir()
        (ws_root / "pyproject.toml").write_text(
            '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
        )

        # Create member package
        member = ws_root / "packages" / "pkg"
        member.mkdir(parents=True)
        (member / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        engine = CheckEngine(member)
        assert engine.context == ProjectContext.MEMBER
        assert engine.workspace_root == ws_root


# --- paper context: packaging checks out, paper checks in -----------------

PAPER_CHECK_IDS = frozenset({"paper.paper_structure", "paper.plan_present"})

# Python-packaging documentation ids a paper must never be graded on.
PACKAGING_DOC_CHECK_IDS = frozenset(
    {
        "docs.diataxis_nav",
        "docs.gen_ref_pages",
        "docs.mkdocs_exists",
        "docs.plugins",
        "docs.readme_badges",
        "docs.standalone_api_ref",
    }
)


def _discovered_ids() -> set[str]:
    """Every canonical check id the discovery registry currently exposes."""
    names = {get_check_name(fn) for fns in ALL_CHECKS.values() for fn in fns}
    return {name for name in names if name is not None}


def _skip_table() -> dict[ProjectContext, frozenset[str]]:
    """The context-keyed skip table the check engine must expose."""
    table: dict[ProjectContext, frozenset[str]] | None = getattr(
        checker, "SKIP_BY_CONTEXT", None
    )
    assert table is not None, "axm_init.core.checker must expose SKIP_BY_CONTEXT"
    return table


def _ran_ids(result: ProjectResult) -> set[str]:
    """The ids the engine actually ran (i.e. NOT excluded) for this project."""
    for attr in ("checks", "results", "check_results"):
        value = getattr(result, attr, None)
        if isinstance(value, list):
            return {check.name for check in value}
    msg = "ProjectResult must expose the list of check results it ran"
    raise AssertionError(msg)


def _excluded_ids(result: ProjectResult) -> set[str]:
    """Ids with status excluded: skipped by context, or excluded by config."""
    explicit = set(getattr(result, "excluded_checks", None) or ())
    return (_discovered_ids() - _ran_ids(result)) | explicit


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


@pytest.mark.integration
def test_paper_project_excludes_every_packaging_check(tmp_path: Path) -> None:
    """AC4: packaging ids are excluded on a paper and no packaging failure remains."""
    project = _paper_project(tmp_path / "paper-x")

    engine = CheckEngine(project)
    result = engine.run()

    assert engine.context == ProjectContext.PAPER
    assert PACKAGING_DOC_CHECK_IDS <= _excluded_ids(result)
    packaging_failures = {
        check.name for check in result.failures if not check.name.startswith("paper.")
    }
    assert packaging_failures == set()


@pytest.mark.integration
def test_paper_project_runs_both_paper_checks(tmp_path: Path) -> None:
    """AC5: check_paper_structure and check_plan_present both run on a paper."""
    project = _paper_project(tmp_path / "paper-x")

    result = CheckEngine(project).run()

    assert PAPER_CHECK_IDS <= _ran_ids(result)
    assert PAPER_CHECK_IDS & _excluded_ids(result) == set()


@pytest.mark.integration
def test_legacy_contexts_keep_their_exact_non_excluded_id_sets(
    tmp_path: Path,
) -> None:
    """AC6: each legacy context runs exactly its expected id set, paper ids out."""
    standalone = tmp_path / "standalone"
    standalone.mkdir()
    (standalone / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    member = workspace / "packages" / "pkg"
    member.mkdir(parents=True)
    (member / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

    skip_table = _skip_table()
    discovered = _discovered_ids()

    for project, context in (
        (standalone, ProjectContext.STANDALONE),
        (workspace, ProjectContext.WORKSPACE),
        (member, ProjectContext.MEMBER),
    ):
        engine = CheckEngine(project)
        assert engine.context == context
        result = engine.run()

        expected = discovered - set(skip_table[context])
        assert _ran_ids(result) == expected
        assert PAPER_CHECK_IDS <= set(skip_table[context])
        assert PAPER_CHECK_IDS & _ran_ids(result) == set()


@pytest.fixture
def protocol_workspace(tmp_path: Path) -> tuple[Path, list[Path]]:
    """Build two declared members with real defects in all protocol checks."""
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "protocol-workspace"\nversion = "0.1.0"\n'
        '[tool.uv.workspace]\nmembers = ["members/*"]\n',
        encoding="utf-8",
    )
    members = []
    for directory, name in (("one", "protocols-demo"), ("two", "protocols-other")):
        domain = name.removeprefix("protocols-")
        member = root / "members" / directory
        package = member / "src" / f"protocols_{domain}"
        action = package / "work" / "exec"
        nodes = action / "nodes"
        nodes.mkdir(parents=True)
        for folder in (package, package / "work", action, nodes):
            (folder / "__init__.py").write_text("", encoding="utf-8")
        (member / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            "[tool.hatch.build.targets.wheel]\n"
            f'packages = ["src/protocols_{domain}"]\n'
            "[tool.axm-init.protocols]\nschema_version = 999\n"
            f'domain = "{domain}"\n'
            '[[tool.axm-init.protocols.units]]\nname = "work"\n'
            "[[tool.axm-init.protocols.units.protocols]]\n"
            'action = "exec"\nprompts = ["missing"]\n',
            encoding="utf-8",
        )
        (nodes / "broken.py").write_text(
            "def perform() -> int:\n    return 1\n", encoding="utf-8"
        )
        (action / "protocol.py").write_text(
            "def wrong_factory() -> None:\n    return None\n", encoding="utf-8"
        )
        (action / "grammar.py").write_text(
            "for item in (1, 2):\n    value = item\n", encoding="utf-8"
        )
        members.append(member)
    return root, members


def _assert_protocol_failure_is_propagated(
    root: Path, member: Path, canonical: str, location: str, defect: str
) -> None:
    """Compare a real member finding with its canonical workspace result."""
    local = next(
        check
        for check in CheckEngine(member, category="protocols").run().checks
        if check.name == canonical
    )
    assert not local.passed
    assert any(location in detail and defect in detail for detail in local.details)
    aggregated = next(
        check
        for check in CheckEngine(root, category="protocols").run().checks
        if check.name == canonical
    )
    assert not aggregated.passed
    member_name = f"protocols-{member.joinpath('src').iterdir().__next__().name[10:]}"
    for detail in local.details:
        assert any(
            member_name in root_detail and detail in root_detail
            for root_detail in aggregated.details
        )


@pytest.mark.integration
def test_remonter_le_defaut_de_composant_sous_sa_regle(
    protocol_workspace: tuple[Path, list[Path]],
) -> None:
    """AC1: preserve component rule, member, file, line and export correction."""
    root, members = protocol_workspace
    _assert_protocol_failure_is_propagated(
        root,
        members[0],
        "protocols.protocol_components",
        "nodes/broken.py:1",
        "__all__",
    )


@pytest.mark.integration
def test_remonter_le_defaut_d_assemblage_sous_sa_regle(
    protocol_workspace: tuple[Path, list[Path]],
) -> None:
    """AC2: propagate the assembly defect under its canonical rule."""
    root, members = protocol_workspace
    _assert_protocol_failure_is_propagated(
        root,
        members[0],
        "protocols.protocol_assembly",
        "protocol.py:1",
        "build_protocol",
    )


@pytest.mark.integration
def test_remonter_le_defaut_de_grammaire_sous_sa_regle(
    protocol_workspace: tuple[Path, list[Path]],
) -> None:
    """AC3: propagate the author grammar defect with member attribution."""
    root, members = protocol_workspace
    _assert_protocol_failure_is_propagated(
        root,
        members[0],
        "protocols.author_grammar",
        "grammar.py:1",
        "module-level business iteration",
    )


@pytest.mark.integration
def test_conserver_tous_les_echecs_de_categorie_des_membres(
    protocol_workspace: tuple[Path, list[Path]],
) -> None:
    """AC4: every discovered member failure retains its rule and all findings."""
    root, members = protocol_workspace
    local_results = [
        CheckEngine(member, category="protocols").run() for member in members
    ]
    root_result = CheckEngine(root, category="protocols").run()
    by_name = {check.name: check for check in root_result.checks}
    assert len(by_name) == len(root_result.checks)
    for member, local in zip(members, local_results, strict=True):
        assert local.failures
        member_name = (
            f"protocols-{member.joinpath('src').iterdir().__next__().name[10:]}"
        )
        for failure in local.failures:
            assert failure.name in by_name
            aggregated = by_name[failure.name]
            assert not aggregated.passed, (member_name, failure.name)
            assert failure.details
            for detail in failure.details:
                assert any(
                    member_name in root_detail and detail in root_detail
                    for root_detail in aggregated.details
                ), (member_name, failure.name, detail)


REGISTRATION_RULE = "protocols.protocol_registration"
DRAFT_RULE = "protocols.protocol_draft"
SKELETON_MARKER = "# axm-init: incomplete-skeleton"


def _registration_project(
    root: Path, *, state: str = "ready", action: str = "exec"
) -> Path:
    """Materialize a declared protocol using the public planner."""
    root.mkdir(parents=True, exist_ok=True)
    metadata_path = root / "pyproject.toml"
    metadata = (
        metadata_path.read_text(encoding="utf-8")
        if metadata_path.exists()
        else '[project]\nname = "protocols-demo"\nversion = "0.1.0"\n'
    )
    declaration = ProtocolScaffoldDecl(
        domain="demo", unit="work", action=action, contracts=[], nodes=[]
    )
    plan = plan_protocol_scaffold(declaration, metadata, {})
    metadata_path.write_text(
        plan.metadata.replace('state = "draft"', f'state = "{state}"'),
        encoding="utf-8",
    )
    for operation in plan.operations:
        assert operation.content is not None
        target = root / operation.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(operation.content, encoding="utf-8")
    (root / f"src/protocols_demo/work/{action}/protocol.py").write_text(
        "from __future__ import annotations\n"
        "from axm_loom import protocol\n"
        "__all__ = ['build_protocol']\n"
        f"GRAPH_NAME = 'demo.work.{action}'\n"
        "def build_protocol():\n"
        f"    return protocol('demo.work.{action}', [])\n",
        encoding="utf-8",
    )
    return root


def _register_graph(root: Path, target: str) -> None:
    """Declare a distribution entry point without loading its target."""
    metadata = root / "pyproject.toml"
    metadata.write_text(
        metadata.read_text(encoding="utf-8")
        + '\n[project.entry-points."axm.graphs"]\n'
        + f'"demo.work.exec" = "{target}"\n',
        encoding="utf-8",
    )


def _required_protocol_failure(project: Path, canonical: str) -> CheckResult:
    """Require discovery and a behavioral failure of the named rule."""
    checks = CheckEngine(project, category="protocols").run().checks
    matches = [check for check in checks if check.name == canonical]
    assert len(matches) == 1, [check.name for check in checks]
    result = matches[0]
    assert not result.passed
    assert result.details
    return result


@pytest.mark.integration
def test_refuser_enregistrement_incompatible_avec_etat(tmp_path: Path) -> None:
    """AC1: distinguish registered draft and unregistered ready declarations."""
    findings = []
    for state in ("draft", "ready"):
        project = _registration_project(tmp_path / state, state=state)
        if state == "draft":
            _register_graph(project, "protocols_demo.work.exec.protocol:build_protocol")
        result = _required_protocol_failure(project, REGISTRATION_RULE)
        assert any(
            "pyproject.toml:" in detail
            and "Correction:" in detail
            and state in detail.lower()
            for detail in result.details
        ), result.details
        findings.append(result.details)
    assert findings[0] != findings[1]


@pytest.mark.integration
def test_refuser_cible_non_resoluble(tmp_path: Path) -> None:
    """AC2: reject absent modules, absent symbols and non-factory bindings."""
    targets = (
        "protocols_demo.absent:build_protocol",
        "protocols_demo.work.exec.protocol:absent",
        "protocols_demo.work.exec.protocol:GRAPH_NAME",
    )
    for index, target in enumerate(targets):
        project = _registration_project(tmp_path / str(index))
        _register_graph(project, target)
        result = _required_protocol_failure(project, REGISTRATION_RULE)
        assert any(
            "pyproject.toml:" in detail
            and target in detail
            and "build_protocol" in detail
            and "Correction:" in detail
            for detail in result.details
        ), result.details


@pytest.mark.integration
def test_identifier_collisions_d_identifiants_inspectes(tmp_path: Path) -> None:
    """AC3: identify both graph declarations locally and across members."""
    local = _registration_project(tmp_path / "local")
    _registration_project(local, action="create")
    second = local / "src/protocols_demo/work/create/protocol.py"
    second.write_text(
        second.read_text(encoding="utf-8").replace(
            "demo.work.create", "demo.work.exec"
        ),
        encoding="utf-8",
    )
    _register_graph(local, "protocols_demo.work.exec.protocol:build_protocol")
    result = _required_protocol_failure(local, REGISTRATION_RULE)
    details = "\n".join(result.details)
    assert "work/exec/protocol.py:" in details
    assert "work/create/protocol.py:" in details
    assert "demo.work.exec" in details

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["members/*"]\n',
        encoding="utf-8",
    )
    for name in ("one", "two"):
        member = _registration_project(workspace / "members" / name)
        metadata = member / "pyproject.toml"
        metadata.write_text(
            metadata.read_text(encoding="utf-8").replace(
                'name = "protocols-demo"', f'name = "protocols-{name}"'
            ),
            encoding="utf-8",
        )
        _register_graph(member, "protocols_demo.work.exec.protocol:build_protocol")
    result = _required_protocol_failure(workspace, REGISTRATION_RULE)
    details = "\n".join(result.details)
    assert "protocols-one" in details and "protocols-two" in details
    assert "demo.work.exec" in details
    assert "protocol.py:" in details


@pytest.mark.integration
def test_refuser_marqueur_dans_protocole_pret(tmp_path: Path) -> None:
    """AC4: report the actual planner marker's source line and correction."""
    project = _registration_project(tmp_path / "ready")
    _register_graph(project, "protocols_demo.work.exec.protocol:build_protocol")
    declaration = ProtocolScaffoldDecl(
        domain="demo", unit="work", action="exec", contracts=[], nodes=[]
    )
    plan = plan_protocol_scaffold(declaration, "", {})
    generated = next(
        operation.content
        for operation in plan.operations
        if str(operation.path).endswith("/protocol.py")
    )
    assert generated is not None
    marker = next(line for line in generated.splitlines() if SKELETON_MARKER in line)
    relative = "src/protocols_demo/work/exec/protocol.py"
    source = project / relative
    source.write_text(source.read_text(encoding="utf-8") + marker + "\n")
    location = _reference_location(project, relative, marker)
    result = _required_protocol_failure(project, DRAFT_RULE)
    assert any(
        location in detail and "Correction:" in detail for detail in result.details
    ), result.details


@pytest.mark.integration
def test_remonter_enregistrement_et_etat_sous_leurs_regles(tmp_path: Path) -> None:
    """AC6: aggregate all four defects with canonical rule and member identity."""
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "ws"\n[tool.uv.workspace]\nmembers = ["members/*"]\n',
        encoding="utf-8",
    )
    for defect in ("draft", "missing", "target", "marker"):
        member = _registration_project(
            root / "members" / defect,
            state="draft" if defect == "draft" else "ready",
        )
        metadata = member / "pyproject.toml"
        metadata.write_text(
            metadata.read_text(encoding="utf-8").replace(
                'name = "protocols-demo"', f'name = "protocols-{defect}"'
            ),
            encoding="utf-8",
        )
        if defect != "missing":
            target = "absent" if defect == "target" else "build_protocol"
            _register_graph(member, f"protocols_demo.work.exec.protocol:{target}")
        if defect == "marker":
            source = member / "src/protocols_demo/work/exec/protocol.py"
            source.write_text(
                source.read_text(encoding="utf-8") + SKELETON_MARKER + "\n",
                encoding="utf-8",
            )
    for canonical, names in (
        (REGISTRATION_RULE, ("draft", "missing", "target")),
        (DRAFT_RULE, ("marker",)),
    ):
        aggregated = _required_protocol_failure(root, canonical)
        for name in names:
            local_result = _required_protocol_failure(
                root / "members" / name, canonical
            )
            for detail in local_result.details:
                assert any(
                    f"protocols-{name}" in item and detail in item
                    for item in aggregated.details
                ), aggregated.details


TICKET_RULE = "protocols.protocol_ticket"
TICKET_PATH = "src/protocols_demo/work/exec/ticket.py"
TICKET_DEFECTS = ("missing-file", "unannounced", "contract", "graph")


@pytest.fixture
def ticket_member(workspace_root: Path) -> Path:
    """Materialize the planner's ticket format without post-copy tasks."""
    member = workspace_root / "packages" / "protocols-demo"
    member.mkdir(parents=True)
    declaration = ProtocolScaffoldDecl(
        domain="demo",
        unit="work",
        action="exec",
        contracts=[ContractDecl(name="request")],
        nodes=[],
        ticket=TicketDecl(ticket_type="demo.job", input_contract="request"),
    )
    plan = plan_protocol_scaffold(
        declaration,
        '[project]\nname = "protocols-demo"\nversion = "0.1.0"\n',
        {},
    )
    (member / "pyproject.toml").write_text(plan.metadata, encoding="utf-8")
    for operation in plan.operations:
        assert operation.content is not None
        target = member / operation.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(operation.content, encoding="utf-8")
    ticket = member / TICKET_PATH
    ticket.write_text(
        ticket.read_text(encoding="utf-8") + "GRAPH_NAME = 'demo.work.exec'\n",
        encoding="utf-8",
    )
    return member


def _introduce_ticket_defect(member: Path, defect: str) -> None:
    """Change one ticket binding, leaving its declared profile in place."""
    ticket = member / TICKET_PATH
    if defect == "missing-file":
        ticket.unlink()
    elif defect == "unannounced":
        metadata = member / "pyproject.toml"
        text = metadata.read_text(encoding="utf-8")
        metadata.write_text(
            "\n".join(
                line
                for line in text.splitlines()
                if not line.startswith("ticket_type =")
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        old, new = (
            ("INPUT_CONTRACT = 'request'", "INPUT_CONTRACT = 'undeclared'")
            if defect == "contract"
            else ("GRAPH_NAME = 'demo.work.exec'", "GRAPH_NAME = 'demo.work.other'")
        )
        text = ticket.read_text(encoding="utf-8")
        assert old in text
        ticket.write_text(text.replace(old, new), encoding="utf-8")


def _ticket_failure(project: Path) -> CheckResult:
    """Require a failed ticket rule through category discovery."""
    checks = CheckEngine(project, category="protocols").run().checks
    matches = [check for check in checks if check.name == TICKET_RULE]
    assert len(matches) == 1, [check.name for check in checks]
    result = matches[0]
    assert not result.passed
    assert result.details
    return result


def _reference_location(member: Path, relative: str, reference: str) -> str:
    """Locate a fixture reference without prescribing generated header length."""
    lines = (member / relative).read_text(encoding="utf-8").splitlines()
    line = next(i for i, text in enumerate(lines, 1) if reference in text)
    return f"{relative}:{line}"


@pytest.mark.integration
@pytest.mark.parametrize("defect", TICKET_DEFECTS[:2])
def test_refuser_presence_declaration_incoherente(
    ticket_member: Path, defect: str
) -> None:
    """AC1: reject either presence mismatch with location and correction."""
    announcement = _reference_location(ticket_member, "pyproject.toml", "ticket_type =")
    declaration = _reference_location(ticket_member, TICKET_PATH, "TICKET_TYPE =")
    _introduce_ticket_defect(ticket_member, defect)

    result = _ticket_failure(ticket_member)

    location = announcement if defect == "missing-file" else declaration
    assert any(
        location in detail
        and TICKET_PATH in detail
        and "Correction:" in detail
        and ("ticket_type" in detail or "TICKET_TYPE" in detail)
        for detail in result.details
    ), result.details


@pytest.mark.integration
def test_refuser_contrat_ticket_non_declare(ticket_member: Path) -> None:
    """AC2: reject an undeclared input contract at its ticket reference."""
    _introduce_ticket_defect(ticket_member, "contract")
    location = _reference_location(ticket_member, TICKET_PATH, "INPUT_CONTRACT =")

    result = _ticket_failure(ticket_member)

    assert any(
        location in detail and "undeclared" in detail and "Correction:" in detail
        for detail in result.details
    ), result.details


@pytest.mark.integration
def test_refuser_graphe_ticket_incoherent(ticket_member: Path) -> None:
    """AC3: report both graph names at the inconsistent ticket reference."""
    _introduce_ticket_defect(ticket_member, "graph")
    location = _reference_location(ticket_member, TICKET_PATH, "GRAPH_NAME =")

    result = _ticket_failure(ticket_member)

    assert any(
        location in detail
        and "demo.work.exec" in detail
        and "demo.work.other" in detail
        for detail in result.details
    ), result.details


@pytest.mark.integration
@pytest.mark.parametrize("defect", TICKET_DEFECTS)
def test_remonter_defauts_ticket_sous_la_regle_ticket(
    workspace_root: Path, ticket_member: Path, defect: str
) -> None:
    """AC4: aggregate each ticket defect under its rule with member attribution."""
    _introduce_ticket_defect(ticket_member, defect)

    local = _ticket_failure(ticket_member)
    aggregated = _ticket_failure(workspace_root)

    for detail in local.details:
        assert any(
            "protocols-demo" in root_detail and detail in root_detail
            for root_detail in aggregated.details
        ), (defect, detail, aggregated.details)
