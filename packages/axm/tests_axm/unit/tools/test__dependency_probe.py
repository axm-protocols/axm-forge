from __future__ import annotations

from importlib import metadata
from types import SimpleNamespace

import pytest

from axm.tools._dependency_probe import closure, declared_optional_requirements


def test_optional_groups_are_selected_without_self_distribution() -> None:
    config = {
        "project": {
            "name": "consumer",
            "optional-dependencies": {
                "codex": ["codex; extra == 'codex'", "absent; python_version < '2'"],
                "cursor": ["cursor"],
                "all": ["consumer[codex,cursor]"],
                "cycle": ["consumer[cycle,all]"],
            },
        }
    }
    assert set(declared_optional_requirements(config)) == {"codex", "cursor"}


def test_missing_optional_edges_do_not_hide_installed_or_required(monkeypatch) -> None:
    distributions = {
        "api": SimpleNamespace(requires=["leaf", "absent; extra == 'missing'"]),
        "leaf": SimpleNamespace(requires=["api[missing]", "consumer[all]"]),
    }

    def distribution(name):
        if name not in distributions:
            raise metadata.PackageNotFoundError(name)
        return distributions[name]

    monkeypatch.setattr(metadata, "distribution", distribution)
    assert closure([], ["api[missing]", "uninstalled"], "consumer") == [
        distributions["api"],
        distributions["leaf"],
    ]
    with pytest.raises(metadata.PackageNotFoundError):
        closure(["uninstalled"], ["api"], "consumer")
    with pytest.raises(metadata.PackageNotFoundError):
        closure(["api[missing]"], ["api[missing]"], "consumer")
