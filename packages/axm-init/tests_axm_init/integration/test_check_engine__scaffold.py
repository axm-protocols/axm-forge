"""Integration: scaffold a node/svelte project, then gold-standard-check it.

Proves the full loop end to end on the real bundled Copier templates: a project
scaffolded with ``framework=<fw>`` is auto-detected as that framework and passes
its own gold-standard checks (node base, plus the svelte delta for svelte).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from axm_init.core.checker import CheckEngine
from axm_init.core.framework import Framework
from axm_init.tools.scaffold import InitScaffoldTool


def _scaffold(tmp_path: Path, framework: str) -> Path:
    """Scaffold a project of *framework* into *tmp_path* and return its root."""
    dest = tmp_path / framework
    result = InitScaffoldTool().execute(
        path=str(dest),
        name="my-app",
        org="acme",
        author="Dev",
        email="dev@example.com",
        framework=framework,
    )
    assert result.success, result.error
    return dest


@pytest.mark.integration
def test_scaffolded_node_project_passes_its_checks(tmp_path: Path) -> None:
    """A scaffolded node project is detected as node and scores 100."""
    dest = _scaffold(tmp_path, "node")
    engine = CheckEngine(dest)
    assert engine.framework is Framework.NODE
    result = engine.run()
    assert result.score == 100


@pytest.mark.integration
def test_scaffolded_svelte_project_passes_its_checks(tmp_path: Path) -> None:
    """A scaffolded svelte project runs node base + svelte delta and scores 100."""
    dest = _scaffold(tmp_path, "svelte")
    engine = CheckEngine(dest)
    assert engine.framework is Framework.SVELTE
    result = engine.run()
    assert result.score == 100
    # The svelte delta check ran on top of the node base checks.
    names = {c.name for c in result.checks}
    assert "config.svelte_config" in names
    assert "package_json.package_json_exists" in names


_PROTOCOL_DECLARATIONS = [
    {
        "action": "exec",
        "contracts": [{"name": "input"}],
        "nodes": [{"name": "run", "contract": "input", "prompt": "run"}],
        "prompts": [{"name": "run", "text": "Execute the declared work."}],
        "phases": [{"name": "build", "nodes": ["run"]}],
    }
]


def _scaffold_protocol_profile(tmp_path: Path, label: str) -> Path:
    """Create a generated, buildable protocol-profile witness."""
    dest = tmp_path / label
    tool = InitScaffoldTool()
    common = {
        "path": str(dest),
        # ``protocols-<domain>`` — what the spec mandates and what the
        # scaffold emits (root module ``protocols_<domain>``).
        "name": "protocols-dev",
        "org": "acme",
        "author": "Dev",
        "email": "dev@example.com",
        "profile": "protocols",
        "domain": "dev",
    }
    project = tool.execute(**common)
    assert project.success, project.error
    protocol = tool.execute(
        **common,
        unit="work",
        protocols=_PROTOCOL_DECLARATIONS,
    )
    assert protocol.success, protocol.error

    metadata = dest / "pyproject.toml"
    metadata.write_text(
        metadata.read_text(encoding="utf-8")
        + (
            "\n[tool.hatch.build.targets.wheel]\n"
            'packages = ["src/axm_dev", "src/protocols_dev"]\n'
            "\n[tool.hatch.build.targets.wheel.force-include]\n"
            '"src/protocols_dev" = "protocols_dev"\n'
        ),
        encoding="utf-8",
    )
    return dest


def _replace_metadata(dest: Path, old: str, new: str) -> None:
    """Replace one exact metadata fragment in a generated witness."""
    metadata = dest / "pyproject.toml"
    body = metadata.read_text(encoding="utf-8")
    assert old in body
    metadata.write_text(body.replace(old, new, 1), encoding="utf-8")


def _assert_localized_failure(result: object, *needles: str) -> None:
    """Require a failed check with a file location and actionable correction."""
    failures = result.failures
    assert failures
    evidence = "\n".join(
        part for failure in failures for part in (*failure.details, failure.fix)
    )
    assert any(
        ".toml" in detail or ".py" in detail
        for failure in failures
        for detail in failure.details
    )
    assert all(failure.fix.strip() for failure in failures)
    assert all(needle in evidence for needle in needles)


@pytest.mark.integration
def test_protocols_category_accepts_generated_profile(tmp_path: Path) -> None:
    """AC1: a generated profile with wheel resources passes protocols checks."""
    dest = _scaffold_protocol_profile(tmp_path, "valid")
    result = CheckEngine(dest, category="protocols").run()
    assert result.checks
    assert not result.failures
    assert result.score == 100


@pytest.mark.integration
def test_protocols_rejects_unknown_schema_version(tmp_path: Path) -> None:
    """AC2: an unknown schema reports metadata location and expected version."""
    dest = _scaffold_protocol_profile(tmp_path, "schema")
    _replace_metadata(dest, "schema_version = 1", "schema_version = 99")
    result = CheckEngine(dest, category="protocols").run()
    _assert_localized_failure(result, "pyproject.toml", "schema_version", "1")


@pytest.mark.integration
def test_protocols_rejects_distribution_domain_mismatch(tmp_path: Path) -> None:
    """AC3: a distribution inconsistent with its domain is localized."""
    dest = _scaffold_protocol_profile(tmp_path, "distribution")
    _replace_metadata(dest, 'name = "protocols-dev"', 'name = "protocols-other"')
    result = CheckEngine(dest, category="protocols").run()
    _assert_localized_failure(result, "pyproject.toml", "protocols-other", "dev")


@pytest.mark.integration
def test_protocols_rejects_module_domain_mismatch(tmp_path: Path) -> None:
    """AC3: a protocol module inconsistent with its domain is localized."""
    dest = _scaffold_protocol_profile(tmp_path, "module")
    (dest / "src" / "protocols_dev").rename(dest / "src" / "protocols_other")
    _replace_metadata(dest, "src/protocols_dev", "src/protocols_other")
    result = CheckEngine(dest, category="protocols").run()
    _assert_localized_failure(result, "protocols_other", "dev")


@pytest.mark.integration
def test_protocols_rejects_invalid_duplicate_and_orphan_metadata(
    tmp_path: Path,
) -> None:
    """AC4: invalid, duplicate, and orphan declarations are distinct findings."""
    invalid = _scaffold_protocol_profile(tmp_path, "invalid")
    (invalid / "src" / "protocols_dev" / "work").rename(
        invalid / "src" / "protocols_dev" / "bad-name"
    )
    _replace_metadata(invalid, 'name = "work"', 'name = "bad-name"')
    invalid_result = CheckEngine(invalid, category="protocols").run()
    _assert_localized_failure(invalid_result, "bad-name")

    duplicate = _scaffold_protocol_profile(tmp_path, "duplicate")
    metadata = duplicate / "pyproject.toml"
    duplicate_table = (
        "\n[[tool.axm-init.protocols.units.protocols]]\n"
        'action = "exec"\n'
        'state = "draft"\n'
        'contracts = ["input"]\n'
        'nodes = ["run"]\n'
        "prompts = []\n"
        'phases = ["build"]\n'
    )
    metadata.write_text(
        metadata.read_text(encoding="utf-8") + duplicate_table,
        encoding="utf-8",
    )
    duplicate_result = CheckEngine(duplicate, category="protocols").run()
    _assert_localized_failure(duplicate_result, "exec")

    orphan = _scaffold_protocol_profile(tmp_path, "orphan")
    _replace_metadata(orphan, 'action = "exec"', 'action = "missing"')
    orphan_result = CheckEngine(orphan, category="protocols").run()
    _assert_localized_failure(orphan_result, "missing")


def _protocol_action_root(dest: Path) -> Path:
    """Return the generated action package used by layout scenarios."""
    return dest / "src" / "protocols_dev" / "work" / "exec"


def _failure_evidence(result: object) -> str:
    """Render failure details and fixes for exact negative assertions."""
    return "\n".join(
        part for failure in result.failures for part in (*failure.details, failure.fix)
    )


@pytest.mark.integration
def test_protocols_layout_reports_each_missing_required_path(
    tmp_path: Path,
) -> None:
    """AC1: every missing required path has its own path and repair finding."""
    mutations = (
        ("protocol", "protocol.py"),
        ("contracts", "contracts"),
        ("nodes", "nodes"),
        ("initializer", "__init__.py"),
    )
    evidence_by_variant: dict[str, str] = {}

    for label, relative_path in mutations:
        dest = _scaffold_protocol_profile(tmp_path, f"layout-{label}")
        missing = _protocol_action_root(dest) / relative_path
        if missing.is_dir():
            shutil.rmtree(missing)
        else:
            missing.unlink()

        result = CheckEngine(dest, category="protocols").run()
        evidence = _failure_evidence(result)
        assert result.failures
        assert str(missing.relative_to(dest)) in evidence
        assert "Correction:" in evidence
        evidence_by_variant[label] = evidence

    assert len(set(evidence_by_variant.values())) == len(mutations)


@pytest.mark.integration
def test_protocols_inventory_reports_declared_component_missing_on_disk(
    tmp_path: Path,
) -> None:
    """AC2: an inventoried contract absent from disk names that declaration."""
    dest = _scaffold_protocol_profile(tmp_path, "declared-missing")
    missing_contract = _protocol_action_root(dest) / "contracts" / "input.py"
    missing_contract.unlink()

    result = CheckEngine(dest, category="protocols").run()
    evidence = _failure_evidence(result)
    assert result.failures
    assert "input" in evidence
    assert "declared" in evidence
    assert "missing" in evidence


@pytest.mark.integration
def test_protocols_inventory_reports_local_component_missing_from_metadata(
    tmp_path: Path,
) -> None:
    """AC2: a local contract absent from inventory names that local component."""
    dest = _scaffold_protocol_profile(tmp_path, "local-uninventoried")
    extra_contract = _protocol_action_root(dest) / "contracts" / "extra.py"
    extra_contract.write_text(
        '"""Local contract deliberately omitted from metadata."""\n',
        encoding="utf-8",
    )

    result = CheckEngine(dest, category="protocols").run()
    evidence = _failure_evidence(result)
    assert result.failures
    assert "extra" in evidence
    assert "local" in evidence
    assert "inventor" in evidence


@pytest.mark.integration
def test_protocols_workspace_propagates_member_layout_failure(
    tmp_path: Path,
) -> None:
    """AC3: a workspace result preserves the failing profiled member identity."""
    workspace = tmp_path / "workspace"
    scaffold = InitScaffoldTool().execute(
        path=str(workspace),
        name="protocols-suite",
        org="acme",
        author="Dev",
        email="dev@example.com",
        workspace=True,
    )
    assert scaffold.success, scaffold.error

    member = workspace / "packages" / "protocols-dev"
    member.mkdir(parents=True)
    profiled_member = _scaffold_protocol_profile(member.parent, member.name)
    missing = _protocol_action_root(profiled_member) / "protocol.py"
    missing.unlink()

    result = CheckEngine(workspace, category="protocols").run()
    evidence = _failure_evidence(result)
    assert result.failures
    assert member.name in evidence
    assert str(missing.relative_to(member)) in evidence


@pytest.mark.integration
def test_protocols_resources_reports_declared_prompt_missing_on_disk(
    tmp_path: Path,
) -> None:
    """AC1: a declared prompt missing on disk reports its path and correction."""
    dest = _scaffold_protocol_profile(tmp_path, "prompt-missing")
    missing = _protocol_action_root(dest) / "prompts" / "run.md"
    missing.unlink()

    result = CheckEngine(dest, category="protocols").run()
    resource_failures = [
        failure
        for failure in result.failures
        if failure.name == "protocols.protocols_resources"
    ]
    assert len(resource_failures) == 1
    failure = resource_failures[0]
    evidence = "\n".join((*failure.details, failure.fix))
    assert str(missing.relative_to(dest)) in evidence
    assert "Correction:" in evidence


@pytest.mark.integration
def test_protocols_resources_reports_prompt_excluded_from_distribution(
    tmp_path: Path,
) -> None:
    """AC2: an existing prompt without build inclusion reports that omission."""
    dest = _scaffold_protocol_profile(tmp_path, "prompt-excluded")
    prompt = _protocol_action_root(dest) / "prompts" / "run.md"
    assert prompt.is_file()
    _replace_metadata(
        dest,
        (
            "\n[tool.hatch.build.targets.wheel.force-include]\n"
            '"src/protocols_dev" = "protocols_dev"\n'
        ),
        "",
    )

    result = CheckEngine(dest, category="protocols").run()
    resource_failures = [
        failure
        for failure in result.failures
        if failure.name == "protocols.protocols_resources"
    ]
    assert len(resource_failures) == 1
    failure = resource_failures[0]
    evidence = "\n".join((*failure.details, failure.fix))
    assert "pyproject.toml" in evidence
    assert "force-include" in evidence
    assert str(prompt.relative_to(dest)) in evidence
