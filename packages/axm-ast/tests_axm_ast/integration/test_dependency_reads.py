from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from axm.tools.write_scope import WriteContract, decide_write_access
from axm_edit.tools.read_file import ReadFileTool

from axm_ast.tools.inspect import InspectTool
from axm_ast.tools.search import SearchTool


@pytest.fixture
def dependency_lane(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    package = tmp_path / "lane"
    package.mkdir()
    (package / "pyproject.toml").write_text(
        '[project]\nname="consumer"\nversion="0"\ndependencies=["external-api"]\n'
    )
    (package / "src").mkdir()
    (package / "src" / "consumer.py").write_text("def local(): pass\n")
    site = tmp_path / "site"
    site.mkdir()
    api = site / "external_api"
    api.mkdir()
    (api / "__init__.py").write_text('raise RuntimeError("must never import")\n')
    (api / "node.py").write_text(
        "def load_tool(name: str) -> object:\n"
        '    """Resolve a registered tool."""\n    return name\n'
    )
    metadata = site / "external_api-1.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: external-api\nVersion: 1\n")
    (metadata / "RECORD").write_text(
        "external_api/__init__.py,,\nexternal_api/node.py,,\n"
    )
    rogue = site / "rogue"
    rogue.mkdir()
    (rogue / "__init__.py").write_text("SECRET = 42\n")
    environment: dict[str, object] = {
        "interpreter": sys.executable,
        "package_root": str(package),
        "pythonpath": [str(site)],
    }
    return package, api, environment


@pytest.mark.integration
def test_dependency_reads_do_not_grant_writes(dependency_lane, monkeypatch):
    package, api, environment = dependency_lane
    contract = WriteContract.from_mapping(
        {
            "execution_root": str(package),
            "allowed_prefixes": ["src"],
            "dependency_environment": environment,
        }
    )
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(package),
                "allowed_prefixes": ["src"],
                "dependency_environment": environment,
            }
        ),
    )
    target = str(api / "node.py")
    assert ReadFileTool().execute(path=str(package), file=target).success
    assert decide_write_access(
        contract, "read_file", {"path": str(package), "file": target}
    ).allowed
    assert not decide_write_access(
        contract, "write_file", {"path": str(package), "file": target}
    ).allowed
    rogue = str(api.parent / "rogue" / "__init__.py")
    assert not ReadFileTool().execute(path=str(package), file=rogue).success
    assert not decide_write_access(
        contract, "read_file", {"path": str(package), "file": rogue}
    ).allowed


@pytest.mark.integration
def test_dotted_dependency_inspection_and_search(dependency_lane, monkeypatch):
    package, _api, environment = dependency_lane
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(package),
                "allowed_prefixes": ["src"],
                "dependency_environment": environment,
            }
        ),
    )
    result = InspectTool().execute(
        path=str(package), symbol="external_api.node.load_tool", source=True
    )
    assert result.success, result.error
    assert "Resolve a registered tool" in str(result.data)
    result = InspectTool().execute(
        path=str(package), symbol="external_api.node", source=True
    )
    assert result.success, result.error
    result = SearchTool().execute(path=str(package), name="external_api.node.load_tool")
    assert result.success and result.data["results"]
    assert not InspectTool().execute(path=str(package), symbol="rogue.SECRET").success
    (_api / "__init__.py").write_text(
        "from .node import load_tool as resolve_tool\n"
        'raise RuntimeError("must never import")\n'
    )
    result = InspectTool().execute(
        path=str(package), symbol="external_api.resolve_tool", source=True
    )
    assert result.success, result.error
    assert "Resolve a registered tool" in str(result.data)


@pytest.mark.integration
def test_refusal_attribution_requires_a_real_unresolved_dependency(dependency_lane):
    from axm.tools.dependency_reads import (
        DependencyEnvironment,
        unresolved_dependency_refusals,
    )

    package, api, environment = dependency_lane
    env = DependencyEnvironment.from_mapping(environment)
    failed = {
        "name": "read_file",
        "arguments": {"path": str(package), "file": str(api / "node.py")},
        "ok": False,
        "result": "read_file | ESCAPE | Path escapes project root",
    }
    assert unresolved_dependency_refusals((failed,), env)
    succeeded = {
        **failed,
        "ok": True,
        "result": "source containing not found in docstring",
    }
    assert not unresolved_dependency_refusals((failed, succeeded), env)
    rogue = {
        **failed,
        "arguments": {
            "path": str(package),
            "file": str(api.parent / "rogue" / "__init__.py"),
        },
    }
    assert not unresolved_dependency_refusals((rogue,), env)
    typo = {
        "name": "ast_inspect",
        "arguments": {"symbol": "external_api.node.typo"},
        "ok": False,
        "result": "Symbol not found",
    }
    assert not unresolved_dependency_refusals((typo,), env)


@pytest.mark.integration
def test_read_authority_rejects_escaping_symlinks(dependency_lane, monkeypatch):
    package, api, environment = dependency_lane
    rogue = api.parent / "rogue" / "__init__.py"
    (api / "escape.py").symlink_to(rogue)
    monkeypatch.setenv(
        "AXM_WRITE_CONTRACT",
        json.dumps(
            {
                "execution_root": str(package),
                "allowed_prefixes": ["src"],
                "dependency_environment": environment,
            }
        ),
    )
    assert (
        not ReadFileTool()
        .execute(path=str(package), file=str(api / "escape.py"))
        .success
    )
    assert (
        not InspectTool()
        .execute(path=str(package), symbol="external_api.escape.SECRET", source=True)
        .success
    )
