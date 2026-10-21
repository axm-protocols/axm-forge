from __future__ import annotations

import sys
import venv
from pathlib import Path

import packaging
import pytest
from axm.tools.dependency_reads import DependencyEnvironment, dependency_read_context
from axm.tools.write_scope import WriteContract
from axm_ast.tools.inspect import InspectTool
from axm_edit.tools.read_file import ReadFileTool


def _distribution(site: Path, name: str, requires: tuple[str, ...] = ()) -> Path:
    module = name.replace("-", "_")
    source = site / module / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        'raise RuntimeError("must never import SDK")\nclass Public:\n    pass\n'
    )
    dist = site / f"{module}-1.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        f"Name: {name}\nVersion: 1\n"
        + "".join(f"Requires-Dist: {req}\n" for req in requires)
    )
    (dist / "RECORD").write_text(f"{module}/__init__.py,,\n")
    return source


@pytest.fixture
def optional_session(tmp_path):
    project = tmp_path / "snapshot"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname="consumer-project"\nversion="0"\ndependencies=[]\n'
        '[dependency-groups]\ndev=["claude"]\n'
        "[project.optional-dependencies]\n"
        "codex=[\"codex[tools]; extra == 'codex'\"]\n"
        'cursor=["cursor"]\nabsent=["not-installed"]\n'
        "inactive=[\"rogue; python_version < '2'\"]\n"
        'all=["Consumer_Project[codex,cursor,all]"]\n'
    )
    site = tmp_path / "site"
    sources = {
        name: _distribution(
            site,
            name,
            ("leaf", "not-installed; extra == 'tools'") if name == "codex" else (),
        )
        for name in ("claude", "codex", "cursor", "leaf", "rogue", "consumer-project")
    }
    isolated = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(isolated)
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    installed = isolated / (
        "Lib/site-packages"
        if sys.platform == "win32"
        else f"lib/python{python_version}/site-packages"
    )
    (installed / "packaging").symlink_to(
        Path(packaging.__file__).parent, target_is_directory=True
    )
    environment = DependencyEnvironment(
        str(
            isolated
            / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        ),
        str(project),
        (str(site),),
    )
    contract = WriteContract(
        str(project),
        allowed_prefixes=(str(project),),
        dependency_environment=environment,
    )
    return project, contract, sources


@pytest.mark.integration
@pytest.mark.parametrize("tool", ["ast_inspect", "read_file"])
def test_tools_share_installed_optional_metadata_authority(optional_session, tool):
    project, contract, sources = optional_session
    with dependency_read_context(contract):
        for name in ("claude", "codex", "cursor", "leaf"):
            result = (
                InspectTool().execute(
                    path=str(project),
                    symbol=f"{name}.Public",
                    source=True,
                )
                if tool == "ast_inspect"
                else ReadFileTool().execute(path=str(project), file=str(sources[name]))
            )
            assert result.success, result.error
            assert "class Public" in str(result.data)
            assert not contract.permits(str(sources[name]))
        for name in ("rogue", "consumer-project"):
            assert (
                not ReadFileTool()
                .execute(
                    path=str(project),
                    file=str(sources[name]),
                )
                .success
            )
            assert (
                not InspectTool()
                .execute(
                    path=str(project),
                    symbol=f"{name.replace('-', '_')}.Public",
                    source=True,
                )
                .success
            )
        assert (
            not InspectTool()
            .execute(
                path=str(project),
                symbol="not_installed.Public",
                source=True,
            )
            .success
        )


@pytest.mark.integration
def test_missing_required_distribution_keeps_resolution_fail_closed(optional_session):
    project, contract, sources = optional_session
    (sources["claude"].parent.parent / "claude-1.dist-info" / "METADATA").write_text(
        "Name: claude\nVersion: 1\nRequires-Dist: not-installed\n"
    )
    with dependency_read_context(contract):
        inspected = InspectTool().execute(
            path=str(project),
            symbol="codex.Public",
            source=True,
        )
        assert not inspected.success
        assert "not-installed" in inspected.error
        with pytest.raises(ValueError, match="not-installed"):
            ReadFileTool().execute(path=str(project), file=str(sources["cursor"]))
