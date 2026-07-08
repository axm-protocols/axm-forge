"""``axm-doctor`` command-line interface (cyclopts).

The CLI is a thin shell: it owns argument parsing and human-facing output but
delegates every operation to the central detect/install/orchestrate functions,
so no business logic is duplicated across the CLI / MCP boundary.

Two commands, two postures:

* ``check`` — the **read-only** report. It prints tool presence, third-party
  auth state and missing (value-free) secrets, then exits 0. It NEVER installs
  and NEVER prompts.
* ``bootstrap`` — the **interactive** path. For each absent tool it shows the
  official install command and installs only on an explicit ``y`` (default No,
  honouring the no-system-install rule); for missing secrets it offers to run
  vault setup. Nothing happens without a yes.
"""

from __future__ import annotations

import sys

import cyclopts

from axm_doctor.detect import detect_auth, detect_tool
from axm_doctor.install import InstallResult, install_command, run_install
from axm_doctor.orchestrate import missing_secrets, provision_missing
from axm_doctor.tools import PROBED_TOOLS, THIRD_PARTY_AUTH

__all__ = ["app", "main"]

app = cyclopts.App(
    name="axm-doctor",
    help="Env bootstrap + auth-status doctor (detect, propose, orchestrate).",
)


def _die(exc: Exception) -> None:
    """Print ``exc`` to stderr and exit 1 (the CLI error-path convention)."""
    print(str(exc), file=sys.stderr)
    raise SystemExit(1)


def _yes(prompt: str) -> bool:
    """Ask ``prompt`` and return True only on an explicit ``y`` (default No).

    A closed/piped stdin (``EOFError`` from :func:`input`) is treated as a
    decline rather than an error, so a non-interactive run never aborts.
    """
    try:
        return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


@app.command
def check() -> None:
    """Print the read-only env report and exit 0; never installs or prompts."""
    try:
        _print_check()
    except Exception as exc:  # noqa: BLE001 # CLI boundary: any error -> exit 1
        _die(exc)


def _print_check() -> None:
    """Render the tool / auth / secret report to stdout."""
    for name in PROBED_TOOLS:
        status = detect_tool(name)
        version = status.version or "-"
        print(f"tool\t{name}\t{status.state}\t{version}")
    for tool in THIRD_PARTY_AUTH:
        auth = detect_auth(tool)
        print(f"auth\t{tool}\t{auth.state}\t{auth.login_cmd or '-'}")
    for secret in missing_secrets():
        print(f"secret\t{secret.group}.{secret.name}\t{secret.setup_hint}")


@app.command
def bootstrap() -> None:
    """Interactively install absent tools and provision secrets on confirmation."""
    try:
        _bootstrap_tools()
        _bootstrap_secrets()
    except Exception as exc:  # noqa: BLE001 # CLI boundary: any error -> exit 1
        _die(exc)


def _install_outcome(name: str, result: InstallResult) -> str:
    """Render the install outcome, keyed on the post-check state / returncode.

    Success is NOT inferred from ``result.executed`` (the command merely ran);
    it requires ``returncode == 0`` and a post-check that no longer reports the
    tool as absent. A run that fails is reported as such, with its return code.
    """
    if not result.executed:
        return f"skipped: {result.command}"
    present = result.post_check is not None and result.post_check.state == "present"
    if result.returncode == 0 and present:
        return f"installed ({name} now present)"
    state = result.post_check.state if result.post_check is not None else "absent"
    return f"install failed (rc={result.returncode}, still {state})"


def _bootstrap_tools() -> None:
    """Offer to install each absent tool; install only on explicit confirm.

    On a non-interactive shell (stdin not a TTY) no prompt is possible, so the
    loop reports why nothing was installed and skips installs entirely —
    mirroring :func:`~axm_doctor.orchestrate.provision_missing`.
    """
    if not sys.stdin.isatty():
        print("non-interactive shell: skipping tool installs")
        return
    for name in PROBED_TOOLS:
        if detect_tool(name).state != "absent":
            continue
        plan = install_command(name)
        if plan is None:
            print(f"{name} is absent (no known install command)", file=sys.stderr)
            continue
        print(f"{name} is absent. Install command: {plan.human_command}")
        confirmed = _yes(f"install {name}?")
        result = run_install(plan, confirm=confirmed)
        print(f"  {_install_outcome(name, result)}")


def _bootstrap_secrets() -> None:
    """Offer to run vault setup for missing secrets; provision only on confirm."""
    secrets = missing_secrets()
    if not secrets:
        return
    for secret in secrets:
        print(f"missing secret {secret.group}.{secret.name} ({secret.setup_hint})")
    confirmed = _yes("run vault setup for the missing secrets?")
    result = provision_missing(confirm=confirmed)
    if result.provisioned:
        print(f"  provisioned secrets for: {', '.join(result.groups)}")
    else:
        detail = f" ({result.reason})" if result.reason else ""
        print(f"  secrets NOT provisioned{detail}")
        if result.still_missing:
            print(f"  still missing: {', '.join(result.still_missing)}")


def main() -> None:
    """Console-script entry point for ``axm-doctor``."""
    app()
