"""Plan immutable Git trees without touching refs, checkout or working files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.tools.release_plan import GitReleasePlanTool

pytestmark = pytest.mark.integration


def manifest(
    name: str = "demo",
    deps: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
    *,
    private: bool = False,
) -> str:
    """Build static Hatch metadata without running a build backend."""
    classifiers = ["Private :: Do Not Upload"] if private else []
    return (
        f"[project]\nname={json.dumps(name)}\ndynamic=['version']\n"
        f"dependencies={json.dumps(list(deps))}\n"
        f"classifiers={json.dumps(classifiers)}\n"
        f"[project.optional-dependencies]\nplugins={json.dumps(list(optional))}\n"
        "[build-system]\nrequires=['hatchling','hatch-vcs']\n"
        "build-backend='hatchling.build'\n"
        f"[tool.hatch.version]\nsource='vcs'\n"
        f"tag-pattern='{name}/v(?P<version>.*)'\n"
    )


def commit(root: Path, files: dict[str, str], message="feat: packages") -> str:
    """Commit fixture files; no release/tag subprocess is launched."""
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    assert run_git(["add", "."], root).returncode == 0
    result = run_git(["commit", "-qm", message], root)
    assert result.returncode == 0, result.stderr
    return run_git(["rev-parse", "HEAD"], root).stdout.strip()


def plan(root: Path, ref: str = "HEAD") -> dict[str, object]:
    result = GitReleasePlanTool().execute(path=str(root), ref=ref)
    assert result.success, result.error
    assert result.data is not None
    return result.data


def test_pinned_workspace_plan_ignores_dirty_files_and_preserves_all_git_state(
    tmp_git_repo,
):
    root = tmp_git_repo
    ref = commit(
        root,
        {
            "pyproject.toml": "[tool.uv.workspace]\nmembers=['packages/*']\n"
            "exclude=['packages/excluded']\n",
            "packages/sdk/pyproject.toml": manifest("sdk", optional=("plugin",)),
            "packages/plugin/pyproject.toml": manifest("plugin", ("sdk>=0.1.0",)),
            "packages/excluded/pyproject.toml": "invalid TOML",
        },
    )
    (root / "packages/sdk/pyproject.toml").write_text("dirty invalid TOML")
    before = run_git(["status", "--porcelain=v1"], root).stdout
    refs = run_git(["show-ref"], root).stdout
    data = plan(root, ref)
    assert data["ref"] == ref
    assert data["order"] == ["sdk", "plugin"]
    assert data["excluded"] == ["pyproject.toml"]
    rows = data["packages"]
    assert rows[0]["optional_requirements"] == ["plugin"]
    assert rows[1]["dependencies"] == ["sdk"]
    assert rows[0]["suggested_next"] == "0.1.0"
    assert run_git(["show-ref"], root).stdout == refs
    assert run_git(["status", "--porcelain=v1"], root).stdout == before
    assert (root / "packages/sdk/pyproject.toml").read_text() == "dirty invalid TOML"


def test_package_scoped_changes_and_completed_tags_are_distinguished(tmp_git_repo):
    root = tmp_git_repo
    commit(
        root,
        {
            "pyproject.toml": "[tool.uv.workspace]\nmembers=['packages/*']\n",
            "packages/a/pyproject.toml": manifest("a"),
            "packages/b/pyproject.toml": manifest("b", private=True),
        },
    )
    assert run_git(["tag", "-a", "a/v0.1.0", "-m", "a"], root).returncode == 0
    assert run_git(["tag", "b/v0.1.0"], root).returncode == 0
    ref = commit(root, {"packages/a/code.txt": "changed"}, "fix: a behavior")
    rows = plan(root)["packages"]
    assert rows[0]["action"] == "release"
    assert rows[0]["suggested_next"] == "0.1.1"
    assert rows[0]["current_tag"] == "a/v0.1.0"
    assert rows[1]["action"] == "unchanged"
    assert rows[1]["private"] is True
    assert rows[1]["suggested_bump"] == "none"
    assert run_git(["tag", "a/v0.1.1", ref], root).returncode == 0
    rows = plan(root)["packages"]
    assert rows[0]["action"] == "already_released"
    assert rows[0]["tag"] == "a/v0.1.1"


def test_recursive_members_and_virtual_members(tmp_git_repo):
    commit(
        tmp_git_repo,
        {
            "pyproject.toml": "[tool.uv.workspace]\nmembers=['libs/**']\n",
            "libs/pyproject.toml": "[tool.uv]\npackage=false\n",
            "libs/core/pyproject.toml": manifest("core"),
            "libs/virtual/pyproject.toml": "[tool.uv]\npackage=false\n",
        },
    )
    data = plan(tmp_git_repo)
    assert data["order"] == ["core"]
    assert "libs/virtual/pyproject.toml" in data["excluded"]


@pytest.mark.parametrize(
    ("root_config", "files", "error"),
    [
        ("[tool.uv.workspace]\nmembers=['../escape']\n", {"x/file": "x"}, "escapes"),
        (
            "[tool.uv.workspace]\nmembers=['packages/*']\n",
            {"packages/missing/README.md": "x"},
            "no pyproject",
        ),
        (
            "[tool.uv.workspace]\nmembers=['packages/*']\n",
            {
                "packages/a/pyproject.toml": manifest("same"),
                "packages/b/pyproject.toml": manifest("same"),
            },
            "Duplicate",
        ),
        (
            "[tool.uv.workspace]\nmembers=['packages/*']\n",
            {
                "packages/a/pyproject.toml": manifest("a", ("b",)),
                "packages/b/pyproject.toml": manifest("b", ("a",)),
            },
            "cycle",
        ),
        ("[tool.uv.workspace]\nmembers=[]\n", {}, "No release packages"),
        (
            manifest().replace(
                "dynamic=['version']", "dynamic=['version','dependencies']"
            ),
            {},
            "Dynamic",
        ),
        (manifest().replace("(?P<version>.*)", "(.*)"), {}, "tag-pattern"),
        (manifest().replace("demo/v(?P", "demo/x(?P"), {}, "prefix"),
        (manifest(deps=("not a valid requirement !",)), {}, "Expected"),
        ("[project]\nname='virtual'\n", {}, "No release packages"),
    ],
)
def test_invalid_inventory_blocks_before_any_release_effect(
    tmp_git_repo, root_config, files, error
):
    commit(tmp_git_repo, {"pyproject.toml": root_config, **files})
    result = GitReleasePlanTool().execute(path=str(tmp_git_repo))
    assert result.success is False
    assert error.lower() in result.error.lower()
    assert run_git(["tag", "--list"], tmp_git_repo).stdout == ""


def test_invalid_revision_and_non_repository_are_errors(tmp_git_repo, tmp_path):
    commit(tmp_git_repo, {"pyproject.toml": manifest()})
    result = GitReleasePlanTool().execute(path=str(tmp_git_repo), ref="missing-ref")
    assert result.success is False
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    result = GitReleasePlanTool().execute(path=str(outside))
    assert result.success is False
    assert "repository" in result.error.lower()


def test_build_requirements_impose_order_even_without_runtime_dependencies(
    tmp_git_repo,
):
    builder = manifest("builder")
    consumer = manifest("consumer").replace(
        "requires=['hatchling','hatch-vcs']", "requires=['builder>=0.1']"
    )
    commit(
        tmp_git_repo,
        {
            "pyproject.toml": "[tool.uv.workspace]\nmembers=['packages/*']\n",
            "packages/a/pyproject.toml": consumer,
            "packages/z/pyproject.toml": builder,
        },
    )
    assert plan(tmp_git_repo)["order"] == ["builder", "consumer"]


def test_captured_tag_commit_is_immune_to_later_ref_changes(tmp_git_repo, monkeypatch):
    from axm_git.core import release_plan
    from axm_git.core.release_inventory import read_inventory

    root = tmp_git_repo
    before = commit(root, {"pyproject.toml": manifest(), "code.txt": "old"})
    assert run_git(["tag", "-a", "demo/v0.1.0", "-m", "old"], root).returncode == 0
    ref = commit(root, {"code.txt": "new"}, "fix: behavior")
    snapshot = read_inventory(root, "HEAD")
    assert (
        run_git(["tag", "-fa", "demo/v0.1.0", "-m", "moved", ref], root).returncode == 0
    )
    monkeypatch.setattr(release_plan, "read_inventory", lambda *_: snapshot)
    row = release_plan.plan_releases(root)["packages"][0]
    assert row["current_tag_commit"] == before
    assert row["action"] == "release"
    assert row["suggested_next"] == "0.1.1"


def test_a_release_tag_pointing_to_a_tree_is_a_blocker(tmp_git_repo):
    commit(tmp_git_repo, {"pyproject.toml": manifest()})
    assert run_git(["tag", "demo/v0.1.0", "HEAD^{tree}"], tmp_git_repo).returncode == 0
    result = GitReleasePlanTool().execute(path=str(tmp_git_repo))
    assert result.success is False
    assert "does not point to a commit" in result.error


@pytest.mark.parametrize(
    "config",
    [
        manifest().replace("dependencies=[]", "dependencies=123"),
        manifest()
        .replace("[project]", "[project]\ninvalid=1")
        .replace(
            "[project.optional-dependencies]\nplugins=[]",
            "[project.optional-dependencies]\nplugins=42",
        ),
        manifest().replace('name="demo"', 'not_name="demo"'),
    ],
)
def test_malformed_static_metadata_is_not_a_successful_empty_plan(tmp_git_repo, config):
    commit(tmp_git_repo, {"pyproject.toml": config})
    result = GitReleasePlanTool().execute(path=str(tmp_git_repo))
    assert result.success is False
    assert result.error
