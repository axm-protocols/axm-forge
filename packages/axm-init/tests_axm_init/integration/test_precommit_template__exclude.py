"""Regression: rendered pre-commit configs exclude fixtures snapshots/goldens.

The mutating basic hooks (``trailing-whitespace`` and ``end-of-file-fixer``)
must not rewrite golden / snapshot fixtures, which are byte-exact baselines.
Every ``.pre-commit-config.yaml.jinja`` template must therefore carry
``exclude: tests/fixtures/(snapshots|goldens)/`` on both hooks, and that
exclude must survive jinja rendering into the scaffolded output.

Covers AC2: render each template and assert the exclude appears on both
mutating hooks in the parsed YAML output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from jinja2 import Environment, select_autoescape

from axm_init.core.templates import TemplateType, get_template_path

pytestmark = [pytest.mark.integration, pytest.mark.scenario_name_ok]

_EXCLUDE = "tests/fixtures/(snapshots|goldens)/"
_MUTATING_HOOKS = ("trailing-whitespace", "end-of-file-fixer")


def _render_precommit(template: TemplateType) -> str:
    """Render the packaged ``.pre-commit-config.yaml.jinja`` for *template*."""
    source = (
        Path(get_template_path(template)) / ".pre-commit-config.yaml.jinja"
    ).read_text()
    return (
        Environment(keep_trailing_newline=True, autoescape=select_autoescape())
        .from_string(source)
        .render(
            package_name="my_pkg",
            module_name="my_pkg",
            member_name="my-pkg",
            workspace_name="my-ws",
        )
    )


def _hook(config: dict[str, object], hook_id: str) -> dict[str, object]:
    """Return the hook mapping with ``id == hook_id`` from a parsed config."""
    repos = config["repos"]
    assert isinstance(repos, list)
    for repo in repos:
        assert isinstance(repo, dict)
        hooks = repo.get("hooks", [])
        assert isinstance(hooks, list)
        for hook in hooks:
            assert isinstance(hook, dict)
            if hook.get("id") == hook_id:
                return hook
    raise AssertionError(f"hook {hook_id!r} not found in rendered config")


@pytest.mark.parametrize(
    "template",
    [
        pytest.param(TemplateType.STANDALONE, id="standalone"),
        pytest.param(TemplateType.WORKSPACE, id="workspace"),
    ],
)
def test_rendered_precommit_excludes_fixtures_on_mutating_hooks(
    template: TemplateType,
) -> None:
    rendered = _render_precommit(template)
    config = yaml.safe_load(rendered)

    assert isinstance(config, dict) and config.get("repos"), "config must parse as YAML"
    for hook_id in _MUTATING_HOOKS:
        hook = _hook(config, hook_id)
        assert hook.get("exclude") == _EXCLUDE, (
            f"{hook_id} must exclude {_EXCLUDE!r}, got {hook.get('exclude')!r}"
        )
