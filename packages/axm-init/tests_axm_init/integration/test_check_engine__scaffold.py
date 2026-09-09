"""Integration: scaffold a node/svelte project, then gold-standard-check it.

Proves the full loop end to end on the real bundled Copier templates: a project
scaffolded with ``framework=<fw>`` is auto-detected as that framework and passes
its own gold-standard checks (node base, plus the svelte delta for svelte).
"""

from __future__ import annotations

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
        "nodes": [{"name": "run", "contract": "input"}],
        "phases": [{"name": "build", "nodes": ["run"]}],
    }
]


def _scaffold_protocol_profile(tmp_path: Path, label: str) -> Path:
    """Create a generated, buildable protocol-profile witness."""
    dest = tmp_path / label
    tool = InitScaffoldTool()
    common = {
        "path": str(dest),
        "name": "axm-dev",
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
    _replace_metadata(dest, 'name = "axm-dev"', 'name = "axm-other"')
    result = CheckEngine(dest, category="protocols").run()
    _assert_localized_failure(result, "pyproject.toml", "axm-other", "dev")


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
