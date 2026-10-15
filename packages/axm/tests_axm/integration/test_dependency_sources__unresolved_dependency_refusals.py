"""Exercise dependency reads through real metadata and static source files."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from axm.tools import dependency_reads
from axm.tools.dependency_reads import (
    DependencyEnvironment,
    dependency_sources,
    unresolved_dependency_refusals,
)

pytestmark = pytest.mark.integration


def test_runner_mapping_canonicalizes_the_project_and_preserves_the_interpreter(
    dependency_project: tuple[DependencyEnvironment, Path], tmp_path: Path
) -> None:
    """Canonical project identity must not erase a lexical interpreter path."""
    environment, _ = dependency_project
    alias = tmp_path / "project-alias"
    alias.symlink_to(environment.package_root, target_is_directory=True)
    raw = environment.to_mapping()
    raw["package_root"] = str(alias)
    restored = DependencyEnvironment.from_mapping(raw)
    assert restored.package_root == environment.package_root
    assert restored.interpreter == environment.interpreter
    assert restored.to_mapping()["pythonpath"] == list(environment.pythonpath)


def test_probe_grants_only_declared_sources_without_importing_them(
    dependency_project: tuple[DependencyEnvironment, Path],
) -> None:
    """Distribution metadata grants package/file roots, never all site-packages."""
    environment, api = dependency_project
    sources = dependency_sources(environment)
    assert set(sources.roots) == {
        ("fixture_api", str(api)),
        ("single", str(api.parent / "single.py")),
    }
    assert sources.permits(api / "types.py")
    assert sources.permits(api.parent / "single.py")
    assert not sources.permits(api.parent)
    assert not sources.permits(api.parent / "rogue" / "__init__.py")


@pytest.mark.parametrize(
    ("query", "filename", "module", "member"),
    [
        ("fixture_api", "__init__.py", "fixture_api", ""),
        ("fixture_api.types", "types.py", "fixture_api.types", ""),
        ("fixture_api.Exported.load", "types.py", "fixture_api.types", "Public.load"),
        ("fixture_api.Absolute", "types.py", "fixture_api.types", "Public"),
        ("fixture_api.module_alias.Public", "types.py", "fixture_api.types", "Public"),
        ("single.Single", "../single.py", "single", "Single"),
    ],
)
def test_static_resolution_follows_module_and_reexport_bindings(
    dependency_project: tuple[DependencyEnvironment, Path],
    query: str,
    filename: str,
    module: str,
    member: str,
) -> None:
    """Aliases resolve to the defining file without running dependency code."""
    environment, api = dependency_project
    assert dependency_sources(environment).resolve_symbol(query) == (
        (api / filename).resolve(),
        module,
        member,
    )


@pytest.mark.parametrize(
    "query", ["fixture_api.cycle_a.Item", "rogue.Secret", "single_extra.X"]
)
def test_cycles_and_unrelated_prefixes_cannot_extend_the_source_closure(
    dependency_project: tuple[DependencyEnvironment, Path], query: str
) -> None:
    """Cyclic reexports terminate and unrelated import prefixes remain absent."""
    environment, api = dependency_project
    sources = dependency_sources(environment)
    assert sources.resolve_symbol("fixture_api.types.Public") == (
        api / "types.py",
        "fixture_api.types",
        "Public",
    )
    assert sources.resolve_symbol(query) is None


def test_dependency_symlinks_cannot_grant_unrelated_sources(
    dependency_project: tuple[DependencyEnvironment, Path],
) -> None:
    """Canonical source authorization rejects both file and directory escapes."""
    environment, api = dependency_project
    (api / "leak.py").symlink_to(api.parent / "rogue" / "__init__.py")
    (api / "leak_dir").symlink_to(api.parent / "rogue", target_is_directory=True)
    sources = dependency_sources(environment)
    assert sources.permits(api / "types.py")
    assert not sources.permits(api / "leak.py")
    assert not sources.permits(api / "leak_dir" / "__init__.py")
    assert sources.resolve_symbol("fixture_api.types.Public") == (
        api / "types.py",
        "fixture_api.types",
        "Public",
    )
    resolved = sources.resolve_symbol("fixture_api.leak")
    assert resolved is None or resolved[0].is_relative_to(api)


def test_missing_distribution_fails_closed(
    dependency_project: tuple[DependencyEnvironment, Path],
) -> None:
    """A failed isolated metadata probe cannot silently grant an empty fallback."""
    environment, _ = dependency_project
    (Path(environment.package_root) / "pyproject.toml").write_text(
        '[project]\nname="consumer"\nversion="0"\n'
        'dependencies=["axm-sdk-nonexistent-distribution"]\n'
    )
    with pytest.raises(ValueError, match="dependency resolution failed"):
        dependency_sources(environment)


def test_invalid_probe_response_is_refused(
    dependency_project: tuple[DependencyEnvironment, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful process exit does not validate a malformed authority response."""
    environment, _ = dependency_project

    def invalid_response(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["probe"], 0, stdout="{}", stderr="")

    monkeypatch.setattr(dependency_reads.subprocess, "run", invalid_response)
    with pytest.raises(ValueError, match="invalid dependency resolution response"):
        dependency_sources(environment)


@pytest.mark.parametrize(
    ("backend", "result"),
    [
        ("read_file", "read_file | ESCAPE | Path escapes project root"),
        ("mcp__sdk__read_file", {"success": False, "error": "Permission denied"}),
        ("read_file", "error: dependency resolution failed"),
        ("read_file", "success: False; path escapes session"),
        ("read_file", "✗ not found"),
    ],
)
def test_refusals_identify_a_declared_dependency_and_success_clears_them(
    dependency_project: tuple[DependencyEnvironment, Path],
    backend: str,
    result: object,
) -> None:
    """Backend evidence survives diagnostics until a later successful read."""
    environment, api = dependency_project
    location = str(api / "types.py")
    failed: dict[str, object] = {
        "name": backend,
        "arguments": {"path": environment.package_root, "file": location},
        "result": result,
        "ok": False,
    }
    refusals = unresolved_dependency_refusals((failed,), environment)
    assert len(refusals) == 1
    assert location in refusals[0]
    assert "arguments=" in refusals[0]
    succeeded = {
        **failed,
        "ok": True,
        "result": {"success": True, "data": "Permission denied appears in a docstring"},
    }
    assert unresolved_dependency_refusals((failed, succeeded), environment) == ()


@pytest.mark.parametrize(
    ("name", "arguments", "attributed"),
    [
        ("ast_inspect", {"symbol": "fixture_api.Exported.load"}, True),
        ("ast_search", {"name": "fixture_api.types.Public"}, True),
        ("ast_inspect", {"symbols": ["single.Single", 4]}, True),
        ("ast_search", {"symbols": "ignored", "name": "fixture_api.types"}, True),
        ("ast_inspect", {"symbol": "fixture_api.types.Public.absent"}, False),
        ("ast_inspect", {"symbol": "single.unrelated.Missing"}, False),
        ("ast_inspect", {"symbol": "fixture_api.cycle_a.Item"}, False),
        ("write_file", {}, False),
        ("read_file", {"file": 4}, False),
        ("read_file", None, False),
    ],
)
def test_symbol_refusals_require_a_real_definition(
    dependency_project: tuple[DependencyEnvironment, Path],
    name: str,
    arguments: object,
    attributed: bool,
) -> None:
    """Typos, unrelated tools and malformed calls are not dependency denials."""
    environment, _ = dependency_project
    call = {
        "name": name,
        "arguments": arguments,
        "result": "Symbol not found",
        "ok": False,
    }
    refusals = unresolved_dependency_refusals((call,), environment)
    if attributed:
        assert len(refusals) == 1
    else:
        assert refusals == ()


@pytest.mark.parametrize(
    "result", ["ordinary tool failure", "source containing not found"]
)
def test_unrelated_files_and_non_access_failures_are_not_misattributed(
    dependency_project: tuple[DependencyEnvironment, Path], result: str
) -> None:
    """Only failed dependency reads with explicit refusal evidence are retained."""
    environment, api = dependency_project
    calls: tuple[dict[str, object], ...] = (
        {
            "name": "read_file",
            "arguments": {"file": str(api.parent / "rogue" / "__init__.py")},
            "ok": False,
            "result": "Permission denied",
        },
        {
            "name": "read_file",
            "arguments": {"file": str(api / "types.py")},
            "ok": result == "source containing not found",
            "result": result,
        },
    )
    assert unresolved_dependency_refusals(calls, environment) == ()
