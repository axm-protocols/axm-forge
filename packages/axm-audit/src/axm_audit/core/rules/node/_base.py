"""Shared base for Node-ecosystem rules.

Every node rule repeats the same preamble: skip cleanly when the project is not
a node project (no ``package.json``), fail loud when the required CLI tool is
not installed locally (never a false green), and treat an env-failure exit
(timeout / missing config) as a hard fail rather than a clean zero-findings run.
``NodeToolRule`` factors that out so each rule only implements ``score_output``.
"""

from __future__ import annotations

import json
import subprocess
from abc import abstractmethod
from pathlib import Path

from axm_audit.core.rules.base import ProjectRule
from axm_audit.core.rules.node._runner import (
    ProcessVerdict,
    interpret_process,
    node_tool_available,
    run_node_tool,
)
from axm_audit.models.results import CheckResult, Severity

__all__ = ["NodeToolRule"]


class NodeToolRule(ProjectRule):
    """Base for a node rule that scores the output of one local CLI tool.

    Subclasses set :attr:`binary` / :attr:`install_hint` and implement
    :meth:`score_output` (and optionally :attr:`args` / :meth:`parse_json`).
    The base handles the no-package.json skip, tool-availability fail-loud, the
    subprocess run, env-failure detection, and JSON parsing.
    """

    binary: str = ""
    """Local node_modules/.bin executable this rule drives (e.g. ``eslint``)."""

    install_hint: str = ""
    """Human hint shown when the binary is not installed."""

    @property
    def args(self) -> list[str]:
        """CLI arguments passed to :attr:`binary` (override per rule)."""
        return []

    @property
    def findings_returncodes(self) -> frozenset[int]:
        """Exit codes that mean "ran fine, reported findings" (not env failure).

        The shared env-failure set treats rc in {2, 124} as a tool that did not
        complete — correct for eslint/ruff/mypy, but ``tsc`` exits **2** when it
        simply *found* type errors. A rule whose tool overloads such a code adds
        it here so the base scores the output instead of failing loud. Default
        is empty (defer entirely to :func:`interpret_process`).
        """
        return frozenset()

    @abstractmethod
    def score_output(self, parsed: object, project_path: Path) -> CheckResult:
        """Turn the parsed tool output into a scored :class:`CheckResult`.

        Args:
            parsed: The parsed stdout (JSON by default, see :meth:`parse_json`).
            project_path: Project root (for relative paths in findings).

        Returns:
            The scored result for this rule.
        """

    def parse(self, result: subprocess.CompletedProcess[str]) -> object:
        """Parse the finished subprocess into the value :meth:`score_output` wants.

        Default: JSON-decode stdout (tolerating empty/invalid output → ``[]``).
        Text tools (``tsc``, ``prettier``) override this to return raw stdout —
        or the combined stdout+stderr when the tool reports on stderr.
        """
        stdout = result.stdout
        if not stdout.strip():
            return []
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []

    def check(self, project_path: Path) -> CheckResult:
        """Run the tool and delegate scoring, with the shared safety preamble."""
        if not (project_path / "package.json").is_file():
            return CheckResult(
                rule_id=self.rule_id,
                passed=True,
                message=f"No package.json — {self.binary} skipped",
                severity=Severity.INFO,
                score=100,
            )
        if not node_tool_available(project_path, self.binary):
            return CheckResult(
                rule_id=self.rule_id,
                passed=False,
                message=f"{self.binary} not available "
                f"(no node_modules/.bin/{self.binary})",
                severity=Severity.ERROR,
                fix_hint=self.install_hint,
            )

        result = run_node_tool(self.binary, self.args, project_path)
        is_findings_code = result.returncode in self.findings_returncodes
        if (
            not is_findings_code
            and interpret_process(result) is ProcessVerdict.ENV_FAILURE
        ):
            return self.env_failure_result(result.returncode)

        return self.score_output(self.parse(result), project_path)

    def env_failure_result(self, returncode: int) -> CheckResult:
        """Fail-loud result when the tool did not complete (timeout/config)."""
        diagnostic = (
            f"audit environment unreliable — {self.binary} did not complete "
            f"(exit code {returncode}: missing config/deps or timeout). "
            f"Run `npm install` and ensure {self.binary} is configured."
        )
        return CheckResult(
            rule_id=self.rule_id,
            passed=False,
            message=f"{self.rule_id} BLOCKED: {diagnostic}",
            severity=Severity.ERROR,
            score=0,
            details={"env_incomplete": True},
            fix_hint=diagnostic,
        )
