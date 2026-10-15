"""Tiny pytest plugin that writes ``audit_test``'s structured result as JSON.

It is loaded by name (``-p axm_audit_report_plugin``) into the *target's*
pytest, whose interpreter does not have axm-audit installed and must not need
any third-party reporting plugin: this module imports nothing but the standard
library and pytest, and uses only long-stable hooks (pytest 7.0 and later).

The destination comes from ``--axm-report-file=PATH``; without it the plugin is
inert. The JSON keeps the shape the runner has always consumed (the one
``pytest-json-report`` produced), restricted to what the runner reads:

- ``summary``: count per test outcome, ``total`` and ``collected``
  (``deselected`` when some were);
- ``tests``: per node ``nodeid``, ``lineno``, ``outcome`` and one entry per
  executed phase (``setup`` / ``call`` / ``teardown``) with ``duration``,
  ``outcome``, ``crash`` (``path``, ``lineno``, ``message``) and ``longrepr``,
  the failure text bounded to head and tail;
- ``collectors``: the collectors that failed, with their bounded ``longrepr``;
- ``duration``, ``root``, ``exitcode``, ``pytest_version`` and ``schema``.
"""

from __future__ import annotations

import json
import os
import time

import pytest

__all__ = [
    "pytest_addoption",
    "pytest_collectreport",
    "pytest_deselected",
    "pytest_runtest_logreport",
    "pytest_sessionfinish",
    "pytest_sessionstart",
]

SCHEMA = 1
OPTION = "--axm-report-file"

# A failure text is kept whole up to this size; beyond it only its head and its
# tail survive (the assertion message is at the end of a pytest traceback, the
# test's own frame at the start), the elided middle being counted.
_MAX_TEXT_CHARS = 12000
_HEAD_CHARS = 2000
_TAIL_CHARS = 10000

type Stage = dict[str, object]
type Record = dict[str, object]


class _Session:
    """What the session recorded so far (one pytest session per process)."""

    config: pytest.Config | None = None
    started: float = 0.0
    deselected: int = 0
    tests: dict[str, Record]
    collectors: list[Record]

    def __init__(self) -> None:
        self.tests = {}
        self.collectors = []


_STATE = _Session()


def _bounded(text: str) -> str:
    """Return *text* whole, or its head and tail around an explicit marker."""
    if len(text) <= _MAX_TEXT_CHARS:
        return text
    elided = len(text) - _HEAD_CHARS - _TAIL_CHARS
    return (
        f"{text[:_HEAD_CHARS]}\n[... {elided} characters elided ...]\n"
        f"{text[-_TAIL_CHARS:]}"
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Declare the report destination option."""
    group = parser.getgroup("axm-audit", "axm-audit structured report")
    group.addoption(
        OPTION,
        dest="axm_report_file",
        default=None,
        help="write the structured test result to this JSON file",
    )


def _active(config: pytest.Config) -> bool:
    # An xdist worker reports to its controller, which owns the file.
    return bool(config.getoption("axm_report_file", None)) and not hasattr(
        config, "workerinput"
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    """Reset the recorded state for the session."""
    global _STATE
    _STATE = _Session()
    _STATE.started = time.time()
    _STATE.config = session.config


def pytest_deselected(items: list[pytest.Item]) -> None:
    """Count the items deselected after collection."""
    _STATE.deselected += len(items)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Record a collector that failed (syntax or import error in a test file)."""
    if not report.failed:
        return
    _STATE.collectors.append(
        {
            "nodeid": report.nodeid,
            "outcome": report.outcome,
            "longrepr": _bounded(str(report.longrepr or "")),
        }
    )


def _stage(report: pytest.TestReport) -> Stage:
    stage: Stage = {"duration": report.duration, "outcome": report.outcome}
    crash = getattr(report.longrepr, "reprcrash", None)
    if crash is not None:
        stage["crash"] = {
            "path": crash.path,
            "lineno": crash.lineno,
            "message": crash.message,
        }
    text = report.longreprtext
    if text:
        stage["longrepr"] = _bounded(text)
    return stage


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record one phase of a test and fold it into the test's outcome."""
    config = _STATE.config
    item = _STATE.tests.setdefault(
        report.nodeid,
        {"nodeid": report.nodeid, "lineno": report.location[1], "outcome": "passed"},
    )
    if config is not None:
        status = config.hook.pytest_report_teststatus(report=report, config=config)
        outcome = status[0]
        if outcome not in ("passed", ""):
            item["outcome"] = outcome
    item[report.when] = _stage(report)


def _summary(session: pytest.Session) -> dict[str, int]:
    summary: dict[str, int] = {}
    for test in _STATE.tests.values():
        outcome = str(test["outcome"])
        summary[outcome] = summary.get(outcome, 0) + 1
    summary["total"] = sum(summary.values())
    deselected = _STATE.deselected
    summary["collected"] = int(session.testscollected) + deselected
    if deselected:
        summary["deselected"] = deselected
    return summary


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write the structured result to the requested file."""
    config = session.config
    if not _active(config) or _STATE.config is None:
        return
    payload = {
        "schema": SCHEMA,
        "pytest_version": pytest.__version__,
        "duration": time.time() - _STATE.started,
        "exitcode": int(exitstatus),
        "root": str(config.rootpath),
        "summary": _summary(session),
        "collectors": _STATE.collectors,
        "tests": list(_STATE.tests.values()),
    }
    path = str(config.getoption("axm_report_file"))
    scratch = f"{path}.{os.getpid()}.tmp"
    with open(scratch, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, default=str)
    os.replace(scratch, path)
