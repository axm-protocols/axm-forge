"""Explicit dependency environments on real fixture commits and hooks."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from axm_git.core.runner import run_git
from axm_git.tools.commit import GitCommitTool


def _environment(repo: Path) -> dict[str, object]:
    """Declare the existing test interpreter and a candidate-only source."""
    package = repo / "packages" / "demo"
    source = package / "src"
    source.mkdir(parents=True)
    (source / "runtime_marker.py").write_text("VALUE = 'candidate'\n")
    return {
        "interpreter": sys.executable,
        "package_root": str(package),
        "pythonpath": [],
    }


def test_hook_receives_declared_python_and_candidate_sources(
    commit_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook gets an isolated environment while the service remains intact."""
    environment = _environment(commit_repo)
    external = commit_repo.with_name(commit_repo.name + "-dependency")
    external.mkdir()
    (external / "runtime_marker.py").write_text("VALUE = 'dependency'\n")
    environment["pythonpath"] = [str(external)]
    monkeypatch.setenv("PYTHONPATH", "/service/source")
    before = dict(os.environ)
    hook = commit_repo / ".git" / "hooks" / "pre-commit"
    hook.write_text(
        "#!/bin/sh\n"
        '"$AXM_DEPENDENCY_INTERPRETER" -c \'import json,sys; '
        "from pathlib import Path; import runtime_marker; "
        'Path(".git/runtime.json").write_text(json.dumps('
        '{"python":sys.executable,"value":runtime_marker.VALUE}))\'\n'
    )
    hook.chmod(0o755)
    (commit_repo / "candidate.txt").write_text("candidate\n")
    result = GitCommitTool().execute(
        path=str(commit_repo),
        commits=[{"files": ["candidate.txt"], "message": "feat: candidate"}],
        dependency_environment=environment,
    )
    assert result.success, result.error
    observed = json.loads((commit_repo / ".git" / "runtime.json").read_text())
    assert observed == {"python": sys.executable, "value": "candidate"}
    assert dict(os.environ) == before


def test_invalid_environment_refuses_before_staging(commit_repo: Path) -> None:
    """A malformed declared interpreter cannot silently fall back to the service."""
    (commit_repo / "candidate.txt").write_text("candidate\n")
    result = GitCommitTool().execute(
        path=str(commit_repo),
        commits=[{"files": ["candidate.txt"], "message": "feat: candidate"}],
        dependency_environment={
            "interpreter": "relative/python",
            "package_root": str(commit_repo),
        },
    )
    assert not result.success
    assert "interpreter" in (result.error or "")
    assert run_git(["diff", "--cached", "--name-only"], commit_repo).stdout == ""
    assert run_git(["log", "-1", "--format=%s"], commit_repo).stdout.strip() == (
        "chore: init"
    )


def test_autofix_keeps_the_declared_environment_on_retry(
    install_hook: Callable[[str], Path],
) -> None:
    """Explicit transport preserves the existing autofix and retry behavior."""
    repo = install_hook("autofix")
    environment = _environment(repo)
    hook = repo / ".git/hooks/pre-commit"
    body = hook.read_text().split("\n", 1)[1]
    hook.write_text(
        "#!/bin/sh\n"
        '"$AXM_DEPENDENCY_INTERPRETER" -c \'import runtime_marker; '
        "print(runtime_marker.VALUE)' >> .git/runtime-calls\n" + body
    )
    (repo / "fix_me.py").write_text("value = 1\n")
    result = GitCommitTool().execute(
        path=str(repo),
        commits=[{"files": ["fix_me.py"], "message": "feat: fixed"}],
        dependency_environment=environment,
    )
    assert result.success, result.error
    assert result.data is not None
    assert result.data["hook_autofixed_files"] == ["fix_me.py"]
    assert (repo / ".git/runtime-calls").read_text().splitlines() == [
        "candidate",
        "candidate",
    ]


def test_commit_message_veto_preserves_preexisting_index(commit_repo: Path) -> None:
    """A message hook veto remains final and only new staging is restored."""
    environment = _environment(commit_repo)
    (commit_repo / "README.md").write_text("preexisting\n")
    run_git(["add", "README.md"], commit_repo)
    (commit_repo / "candidate.txt").write_text("candidate\n")
    hook = commit_repo / ".git" / "hooks" / "commit-msg"
    hook.write_text("#!/bin/sh\nprintf 'scripted message veto' >&2\nexit 1\n")
    hook.chmod(0o755)
    result = GitCommitTool().execute(
        path=str(commit_repo),
        commits=[
            {"files": ["README.md", "candidate.txt"], "message": "feat: candidate"}
        ],
        dependency_environment=environment,
    )
    assert not result.success
    assert result.data is not None
    failed = result.data["failed_commit"]
    assert isinstance(failed, dict)
    assert "scripted message veto" in str(failed["precommit_output"])
    assert run_git(["diff", "--cached", "--name-only"], commit_repo).stdout.strip() == (
        "README.md"
    )


def test_two_real_commit_invocations_keep_distinct_candidate_sources(
    commit_repo: Path,
) -> None:
    """Overlapping fixture hooks cannot import the other invocation's candidate."""
    from concurrent.futures import ThreadPoolExecutor
    from shutil import copytree

    peer = commit_repo.with_name(commit_repo.name + "-peer")
    copytree(commit_repo, peer)
    environments = {}
    for repo, marker in ((commit_repo, "first"), (peer, "second")):
        environments[repo] = _environment(repo)
        (repo / "packages/demo/src/runtime_marker.py").write_text(
            f"VALUE = {marker!r}\n"
        )
        (repo / "candidate.txt").write_text(marker + "\n")
        hook = repo / ".git/hooks/pre-commit"
        hook.write_text(
            "#!/bin/sh\n"
            '"$AXM_DEPENDENCY_INTERPRETER" -c \'from pathlib import Path; '
            "import runtime_marker,time; time.sleep(0.05); "
            'Path(".git/observed").write_text(runtime_marker.VALUE)\'\n'
        )
        hook.chmod(0o755)

    def commit(repo: Path) -> bool:
        return (
            GitCommitTool()
            .execute(
                path=str(repo),
                commits=[{"files": ["candidate.txt"], "message": "feat: isolated"}],
                dependency_environment=environments[repo],
            )
            .success
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(commit, (commit_repo, peer))) == [True, True]
    assert (commit_repo / ".git/observed").read_text() == "first"
    assert (peer / ".git/observed").read_text() == "second"
