"""Integration tests for the build_prompt -> harness_fix options contract."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from axm_edit.services.lint import build_prompt, harness_fix
from tests.integration._helpers import _make_errors

pytestmark = pytest.mark.integration


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with a Python file containing an unfixable ruff error."""
    src = tmp_path / "app.py"
    src.write_text("try:\n    x = 1\nexcept:\n    pass\n")
    return tmp_path


def _harness_run(output: str) -> SimpleNamespace:
    """Minimal HarnessRun stub exposing the ``output`` field."""
    return SimpleNamespace(output=output)


class TestOptionsContract:
    """AC1, AC3: run() receives system_prompt, cwd, response_schema, prompt."""

    def test_options_contract(self, project: Path, mocker: Any) -> None:
        """AC1, AC3: options passed to run() carry the full fix contract."""
        mocker.patch("axm_edit.services.lint.get_adapter", return_value=mocker.Mock())
        captured: dict[str, Any] = {}

        async def _run(
            adapter: Any, prompt: str, options: Any = None
        ) -> SimpleNamespace:
            captured["prompt"] = prompt
            captured["options"] = dict(options or {})
            return _harness_run("[]")

        mocker.patch("axm_edit.services.lint.run", side_effect=_run)

        errors = _make_errors("app.py", ["E722"], line=3)
        harness_fix(project, errors)

        options = captured["options"]
        # System prompt carries the anti-fabrication rules
        assert "NEVER create new function" in options["system_prompt"]
        assert options["cwd"] == str(project)
        # response_schema imposes a JSON array of {old, new} objects
        schema_dump = json.dumps(options["response_schema"])
        assert '"old"' in schema_dump
        assert '"new"' in schema_dump
        # Prompt comes from build_prompt
        assert captured["prompt"] == build_prompt(project / "app.py", errors)
