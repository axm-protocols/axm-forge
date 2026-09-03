from __future__ import annotations

import ast
import importlib
from types import ModuleType


def _subject() -> ModuleType:
    return importlib.import_module(
        "axm_audit.core.rules.practices.tool_secret_locations"
    )


def test_auth_detection_module_path_is_discriminated() -> None:
    """AC1: auth-detection paths are distinguished from ordinary paths."""
    subject = _subject()

    assert subject.is_auth_detection_module("src/pkg/auth/detect.py") is True
    assert subject.is_auth_detection_module("src/pkg/core/report.py") is False


def test_third_party_session_path_literal_is_located() -> None:
    """AC2: a third-party session path reports its kind, value, and line."""
    subject = _subject()
    tree = ast.parse('SESSION = "~/.claude/.credentials.json"')

    locations = subject.find_tool_session_path_literals(
        tree,
        first_party=frozenset({"axm"}),
    )

    assert len(locations) == 1
    assert locations[0].kind == "session_path"
    assert locations[0].value == "~/.claude/.credentials.json"
    assert locations[0].line == 1


def test_session_path_literal_is_namespace_relative() -> None:
    """AC3: the same session path flips with the first-party namespace."""
    subject = _subject()
    tree = ast.parse('P = "~/.acme/auth.json"')

    foreign_locations = subject.find_tool_session_path_literals(
        tree,
        first_party=frozenset({"axm"}),
    )
    first_party_locations = subject.find_tool_session_path_literals(
        tree,
        first_party=frozenset({"acme"}),
    )

    assert len(foreign_locations) == 1
    assert first_party_locations == []


def test_keyring_service_literal_requires_call_position() -> None:
    """AC4: a keyring service is reported only in a keyring call position."""
    subject = _subject()
    call_tree = ast.parse('keyring.get_password("Claude Code-credentials", user)')
    assignment_tree = ast.parse('LABEL = "Claude Code-credentials"')

    call_locations = subject.find_tool_keyring_service_literals(
        call_tree,
        first_party=frozenset({"axm"}),
    )
    assignment_locations = subject.find_tool_keyring_service_literals(
        assignment_tree,
        first_party=frozenset({"axm"}),
    )

    assert len(call_locations) == 1
    assert call_locations[0].kind == "keyring_service"
    assert call_locations[0].value == "Claude Code-credentials"
    assert assignment_locations == []
