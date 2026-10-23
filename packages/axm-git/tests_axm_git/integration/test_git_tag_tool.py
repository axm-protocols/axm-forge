"""Integration tests for GitTagTool against real and mocked git repositories."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from axm_git.core.runner import run_git
from axm_git.tools import tag as tag_mod
from axm_git.tools.tag import GitTagTool, get_tag_prefix


@pytest.fixture(autouse=True)
def _route_verification_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Share each test's Git boundary mock with the extracted verifier."""

    def call(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return tag_mod.run_git(args, cwd)

    monkeypatch.setattr("axm_git.core.tag_verification.run_git", call)


def _mock_completed(
    stdout: str = "",
    stderr: str = "",
    rc: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Create a mock CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=rc,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.mark.integration
class TestFullTagAgainstRealRepo:
    """Tagging a workspace preserves its environment and publishes exact Git refs."""

    @pytest.mark.parametrize("prefix", ["", "pkg/"])
    @pytest.mark.parametrize("move_local_tag", [False, True])
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    def test_full_tag_matches_created_ref(
        self,
        _gh: MagicMock,
        tmp_workspace_repo: tuple[Path, Path],
        prefix: str,
        move_local_tag: bool,
    ) -> None:
        """A real local push works with Git alone; no package manager is invoked."""
        root, package = tmp_workspace_repo
        remote = root.parent / "origin.git"
        run_git(["init", "--bare", str(remote)], root)
        run_git(["remote", "add", "origin", str(remote)], root)
        (root / ".gitignore").write_text(".venv/\n")
        (package / "pyproject.toml").write_text(
            '[project]\nname = "example"\n'
            '[tool.hatch.version]\nsource = "vcs"\n'
            f'tag-pattern = "{prefix}v(?P<version>.*)"\n'
        )
        metadata = (
            root / ".venv/lib/python3.12/site-packages/sibling.dist-info/METADATA"
        )
        metadata.parent.mkdir(parents=True)
        metadata.write_text("Name: sibling\nVersion: 9.8.7\n")
        (root / "uv.lock").write_text("# lock must not change\n")
        generated = package / "src/_version.py"
        generated.write_text('__version__ = "untouched"\n')
        run_git(["add", "."], root)
        run_git(["commit", "-m", "feat: prepare release"], root)
        head = run_git(["rev-parse", "HEAD"], root).stdout.strip()
        before = {p: p.read_bytes() for p in [metadata, root / "uv.lock", generated]}
        original_run = subprocess.run

        def git_only(
            args: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            assert args[0] == "git", f"Unexpected environment-mutating command: {args}"
            if args[1] == "push" and move_local_tag:
                # A concurrent writer replaces the ref after verification.
                original_run(
                    ["git", "update-ref", f"refs/tags/{prefix}v1.2.3", head],
                    cwd=root,
                    check=True,
                    capture_output=True,
                )
            return original_run(args, **kwargs)

        with patch("subprocess.run", side_effect=git_only):
            result = GitTagTool().execute(path=str(package), version="1.2.3")

        assert result.success, result.error
        assert result.data["full_tag"] == f"{prefix}v1.2.3"
        assert result.data["resolved_version"] == "1.2.3"
        assert result.data["version_source"] == "git_tag"
        assert result.data["tag_commit"] == head
        assert result.data["remote_verified"] is True
        assert {p: p.read_bytes() for p in before} == before
        assert run_git(["status", "--porcelain"], root).stdout == ""
        assert (
            run_git(
                ["rev-parse", f"refs/tags/{prefix}v1.2.3^{{commit}}"], remote
            ).stdout.strip()
            == head
        )
        assert _ref(remote, f"{prefix}v1.2.3") == result.data["tag_object"]
        assert (
            run_git(["cat-file", "-t", result.data["tag_object"]], remote).stdout
            == "tag\n"
        )


_IDENTITY = ["-c", "user.name=Other", "-c", "user.email=other@test.com"]


@dataclass(frozen=True)
class _Release:
    """A package ready to tag, with a local bare repository as ``origin``."""

    root: Path
    package: Path
    origin: Path
    head: str

    def tag(self, version: str = "1.2.3") -> Any:
        return GitTagTool().execute(path=str(self.package), version=version)


def _ref(repo: Path, full_tag: str) -> str:
    """Object id of ``refs/tags/<full_tag>`` in *repo*, or ``""`` if absent."""
    result = run_git(["rev-parse", "--verify", "-q", f"refs/tags/{full_tag}"], repo)
    return result.stdout.strip()


def _bare(path: Path, root: Path) -> Path:
    run_git(["init", "--bare", "-b", "main", str(path)], root)
    run_git(["push", str(path), "HEAD:refs/heads/main"], root)
    return path


@pytest.fixture(params=["", "ast/"], ids=["plain", "monorepo"])
def release(
    request: pytest.FixtureRequest,
    tmp_workspace_repo: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> _Release:
    """Real workspace repo whose package tags as ``{prefix}vX.Y.Z``."""
    monkeypatch.setattr("axm_git.tools.tag.gh_available", lambda: False)
    root, package = tmp_workspace_repo
    (package / "pyproject.toml").write_text(
        '[project]\nname = "example"\n'
        '[tool.hatch.version]\nsource = "vcs"\n'
        f'tag-pattern = "{request.param}v(?P<version>.*)"\n'
    )
    run_git(["add", "."], root)
    run_git(["commit", "-m", "feat: prepare release"], root)
    origin = _bare(root.parent / "origin.git", root)
    run_git(["remote", "add", "origin", str(origin)], root)
    head = run_git(["rev-parse", "HEAD"], root).stdout.strip()
    return _Release(root, package, origin, head)


def _full_tag(release: _Release, version: str = "1.2.3") -> str:
    return f"{get_tag_prefix(release.package)}v{version}"


@pytest.mark.integration
class TestTagPublicationFailures:
    """Failure paths against real repositories and a local bare origin."""

    def test_existing_remote_tag_rejects_push_and_is_preserved(
        self, release: _Release
    ) -> None:
        full_tag = _full_tag(release)
        run_git(
            [*_IDENTITY, "tag", "-a", full_tag, release.head, "-m", "theirs"],
            release.origin,
        )
        theirs = _ref(release.origin, full_tag)

        result = release.tag()

        assert not result.success
        assert "push to origin failed" in (result.error or "")
        assert result.data["pushed"] is False
        assert result.data["remote_verified"] is False
        assert _ref(release.origin, full_tag) == theirs
        assert _ref(release.root, full_tag) == result.data["tag_object"] != theirs

    def test_unreachable_origin_keeps_local_tag(self, release: _Release) -> None:
        missing = release.root.parent / "missing.git"
        run_git(["remote", "set-url", "origin", str(missing)], release.root)

        result = release.tag()

        assert not result.success
        assert result.data["pushed"] is False
        assert result.data["remote_verified"] is False
        assert result.data["tag_commit"] == release.head
        assert _ref(release.root, _full_tag(release)) == result.data["tag_object"]
        assert "kept locally · not pushed" in (result.text or "")

    def test_unreadable_origin_after_push_is_not_success(
        self, release: _Release
    ) -> None:
        """Push lands (push URL) but ls-remote reads a missing fetch URL."""
        missing = release.root.parent / "missing.git"
        run_git(["remote", "set-url", "origin", str(missing)], release.root)
        run_git(
            ["remote", "set-url", "--push", "origin", str(release.origin)],
            release.root,
        )

        result = release.tag()

        assert not result.success
        assert "Cannot verify remote tag" in (result.error or "")
        assert result.data["pushed"] is True
        assert result.data["remote_verified"] is False
        assert _ref(release.origin, _full_tag(release)) == result.data["tag_object"]

    def test_lightweight_remote_tag_is_a_mismatch(self, release: _Release) -> None:
        """Origin advertising a lightweight tag (no peeled line) never verifies."""
        full_tag = _full_tag(release)
        mirror = _bare(release.root.parent / "mirror.git", release.root)
        run_git(["tag", full_tag, release.head], mirror)
        run_git(["remote", "set-url", "origin", str(mirror)], release.root)
        run_git(
            ["remote", "set-url", "--push", "origin", str(release.origin)],
            release.root,
        )

        result = release.tag()

        assert not result.success
        assert "lightweight" in (result.error or "")
        assert result.data["pushed"] is True
        assert result.data["remote_verified"] is False
        assert _ref(mirror, full_tag) == release.head

    def test_tag_moved_before_verification_is_not_pushed(
        self, release: _Release
    ) -> None:
        """A tag that no longer peels to the pinned commit is never published."""
        full_tag = _full_tag(release)
        parent = run_git(["rev-parse", "HEAD~1"], release.root).stdout.strip()
        original_run = subprocess.run

        def move_after_create(
            args: list[str], **kwargs: Any
        ) -> subprocess.CompletedProcess[str]:
            completed = original_run(args, **kwargs)
            if args[1:3] == ["tag", "-a"]:
                original_run(
                    ["git", "tag", "-f", "-a", full_tag, parent, "-m", "moved"],
                    cwd=release.root,
                    check=True,
                    capture_output=True,
                )
            return completed

        with patch("subprocess.run", side_effect=move_after_create):
            result = release.tag()

        assert not result.success
        assert "failed verification" in (result.error or "")
        assert "targets" in (result.error or "")
        assert result.data["pushed"] is False
        assert result.data["remote_verified"] is False
        assert _ref(release.origin, full_tag) == ""
        assert (
            run_git(
                ["rev-parse", f"refs/tags/{full_tag}^{{commit}}"], release.root
            ).stdout.strip()
            == parent
        )

    def test_invalid_version_creates_no_tag(self, release: _Release) -> None:
        result = release.tag(version="1.2")

        assert not result.success
        assert "Invalid semver" in (result.error or "")
        assert run_git(["tag", "--list"], release.root).stdout == ""
        assert run_git(["tag", "--list"], release.origin).stdout == ""


@pytest.mark.integration
class TestFullTagData:
    """full_tag/tag data exposure (public-import boundary, real I/O)."""

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    @patch("axm_git.tools.tag.get_tag_prefix", return_value="git/")
    def test_result_exposes_full_tag(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """AC1, AC2: data carries the prefixed full_tag and keeps bare tag."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("git/v0.3.1")
            if args[0] == "log":
                return _mock_completed("abc feat: new api")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["full_tag"] == "git/v0.4.0"
        assert result.data["tag"] == "v0.4.0"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    @patch("axm_git.tools.tag.get_tag_prefix", return_value="")
    def test_empty_prefix_full_tag_equals_tag(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """AC3: empty tag_prefix yields full_tag == tag (no spurious prefix)."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v1.2.2")
            if args[0] == "log":
                return _mock_completed("abc fix: bug")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test", version="1.2.3")
        assert result.success
        assert result.data["full_tag"] == result.data["tag"] == "v1.2.3"


class TestGitTagTool:
    """Test GitTagTool behavior."""

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    def test_success_auto_version(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.7.0")
            if args[0] == "log":
                return _mock_completed("abc feat: new api\ndef fix: bug")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["tag"] == "v0.8.0"
        assert result.data["bump"] == "minor"

    @pytest.mark.parametrize(
        ("version_input", "expected_tag"),
        [
            pytest.param("v9.0.0", "v9.0.0", id="with_v_prefix"),
            pytest.param("2.0.0", "v2.0.0", id="no_v_prefix_added"),
        ],
    )
    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    def test_version_override(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
        version_input: str,
        expected_tag: str,
    ) -> None:
        """Explicit version override produces expected tag.

        Adds v prefix if missing.
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test", version=version_input)
        assert result.success
        assert result.data["tag"] == expected_tag

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    def test_no_existing_tags(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """First tag ever — base is v0.0.0."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("")  # no tags
            if args[0] == "log":
                return _mock_completed("abc feat: init")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert result.data["tag"] == "v0.1.0"
        assert result.data["current_tag"] == "none"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    def test_tag_create_failure(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Tag creation failure reports error."""

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            if args[0] == "tag" and "-a" in args:
                return _mock_completed(stderr="tag already exists", rc=128)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert "Failed to create tag" in (result.error or "")

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    def test_push_failure_reports_false_green(
        self,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Push failure is a hard failure — success=False, pushed=False.

        False-green guard: the annotated tag is created locally but the
        remote push failed, so the Publish CI will never fire. The tool
        must NOT report success (an agent/warden that trusts ``success``
        would believe the release shipped). The local tag is preserved in
        ``data`` for recovery.
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.1.0")
            if args[0] == "log":
                return _mock_completed("abc fix: x")
            if args[0] == "push":
                return _mock_completed(stderr="rejected", rc=1)
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert not result.success
        assert result.data["pushed"] is False
        assert result.data["full_tag"] == "v0.1.1"
        assert "push to origin failed" in (result.error or "")
        assert "rejected" in (result.error or "")


class TestTagPrefixExecution:
    """Regression tests for tag prefix in execute()."""

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    @patch("axm_git.tools.tag.get_tag_prefix", return_value="git/")
    def test_tag_execute_uses_prefix(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Tag is created with prefix from tag-pattern."""
        created_tags: list[str] = []

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("")  # no existing tags
            if args[0] == "log":
                return _mock_completed("abc feat: init")
            if args[0] == "tag" and "-a" in args:
                created_tags.append(args[2])  # capture the tag name
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert created_tags == ["git/v0.1.0"]
        assert result.data["tag"] == "v0.1.0"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    @patch("axm_git.tools.tag.get_tag_prefix", return_value="")
    def test_tag_execute_standalone_no_prefix(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """Standalone repo (no tag-pattern) creates plain v* tags."""
        created_tags: list[str] = []

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("v0.7.0")
            if args[0] == "log":
                return _mock_completed("abc feat: new api")
            if args[0] == "tag" and "-a" in args:
                created_tags.append(args[2])
                return _mock_completed("")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test")
        assert result.success
        assert created_tags == ["v0.8.0"]
        assert result.data["tag"] == "v0.8.0"

    @patch("axm_git.tools.tag.run_git")
    @patch("axm_git.tools.tag.gh_available", return_value=False)
    @patch("axm_git.tools.tag._head_sha", return_value="a" * 40)
    @patch("axm_git.tools.tag.get_tag_prefix", return_value="git/")
    def test_override_with_prefixed_current_tag(
        self,
        _prefix: MagicMock,
        _pkg: MagicMock,
        _gh: MagicMock,
        mock_git: MagicMock,
    ) -> None:
        """A version override succeeds when a *prefixed* tag already exists.

        Regression for P0-2: ``resolve_version`` must strip ``tag_prefix``
        from the current tag before ``parse_tag`` — otherwise
        ``parse_tag("git/v0.4.0")`` raised "Invalid semver tag" and every
        follow-up release was blocked.
        """

        def _side_effect(
            args: list[str], cwd: Any, **kw: Any
        ) -> subprocess.CompletedProcess[str]:
            if args[0] == "rev-parse":
                return _mock_completed("a" * 40)
            if args[0] == "ls-remote":
                return _mock_completed(
                    "\n".join(f"{'a' * 40}\t{ref}" for ref in args[-2:])
                )
            if args[0] == "tag" and "--sort=-v:refname" in args:
                return _mock_completed("git/v0.4.0")
            if args[0] == "log":
                return _mock_completed("abc feat: x")
            return _mock_completed("")

        mock_git.side_effect = _side_effect
        result = GitTagTool().execute(path="/tmp/test", version="0.5.0")
        assert result.success
        assert result.data["full_tag"] == "git/v0.5.0"
        assert result.data["tag"] == "v0.5.0"
