"""Mandatory dependency ordering is independent of the operator's platform."""

from __future__ import annotations

import pytest

from axm_git.core.release_inventory import Package
from axm_git.core.release_plan import release_order
from axm_git.core.semver import release_suggestion


def package(name: str, *requires: str, optional: tuple[str, ...] = ()) -> Package:
    """Make an in-memory distribution for the ordering contract."""
    return Package(name, name, f"{name}/v", requires, optional, False)


def test_dependency_order_is_stable_and_respects_build_and_runtime_edges():
    packages = (
        package("consumer", "SDK_Core[server]>=1; sys_platform == 'win32'"),
        package("sdk-core", "builder"),
        package("builder"),
        package("independent"),
    )
    assert release_order(packages) == ["builder", "independent", "sdk-core", "consumer"]
    assert release_order(tuple(reversed(packages))) == release_order(packages)


def test_plugin_extras_do_not_create_a_mandatory_cycle():
    packages = (
        package("sdk", optional=("plugin",)),
        package("plugin", "sdk"),
    )
    assert release_order(packages) == ["sdk", "plugin"]


@pytest.mark.parametrize(
    "packages",
    [(package("a", "b"), package("b", "a")), (package("self", "self"),)],
)
def test_mandatory_cycles_are_explicit_blockers(packages):
    with pytest.raises(ValueError, match="Mandatory release dependency cycle"):
        release_order(packages)


@pytest.mark.parametrize(
    ("subjects", "tag", "expected"),
    [
        (["fix: first"], None, ("patch", "0.1.0", False)),
        (["feat!: first"], None, ("minor", "0.1.0", True)),
        (["feat: first"], None, ("minor", "0.1.0", False)),
        (["fix: x"], "pkg/v0.2.0", ("patch", "0.2.1", False)),
        (["feat: x"], "pkg/v0.2.0", ("minor", "0.3.0", False)),
        (["feat!: x"], "pkg/v1.2.0", ("major", "2.0.0", True)),
    ],
)
def test_workspace_and_single_package_share_release_version_rules(
    subjects, tag, expected
):
    assert release_suggestion(subjects, tag) == expected
