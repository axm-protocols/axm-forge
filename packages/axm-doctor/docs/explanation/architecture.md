# Architecture

Doctor follows **detect → propose → orchestrate**, wrapped by the CLI and two
request–response AXM tools.

## Ownership

| Module | Responsibility |
| --- | --- |
| detect | PATH/version, declared auth probes, config signals |
| install | Describe plans, execute only with confirmation |
| credentials | Convert vault provenance into typed rows |
| orchestrate | Identify missing credentials and delegate setup |
| cli | Human reports and bootstrap confirmation |
| tools | env_doctor and auth_status ToolResult responses |

Providers own authentication knowledge; vault owns resolution and credential
setup; axm-config owns non-sensitive configuration. Doctor owns no credential
store. Auth dependencies are not provisionable secrets.

## Imports and I/O

Root exports resolve lazily through PEP 562. Importing the root or detection
module does not eagerly import AXM dependencies; pydantic is still required.
Auth discovery and git config checks load deferred dependencies when called.
Full environment reports use axm-config and axm-vault.

Reports contain metadata rather than credential values. This does not imply
no reads or subprocesses: the git check retrieves a non-sensitive config
value; git/gh stdout is captured and discarded. Providers and vault resolution
can perform their own I/O. Doctor does not impose a universal credential-file
size rule or keychain authentication rule.

## Observation, policy and application

ToolResult.success=True means report construction succeeded, not that a machine
is ready. The caller chooses a policy; CLI --strict has a fixed policy documented
in [the reference](../reference/cli.md). DAG callers must map tool_node outputs
explicitly and evaluate observations.

Building a plan runs nothing. Dry-run installation neither installs nor probes.
Dry-run provisioning reads the live catalog/provenance without writing.
Confirmed calls can install or delegate credential writes. Post-checks improve
reporting but do not provide rollback or transactional isolation.

The read-only tools return values through MCP, generic CLI and DAG nodes.
The dedicated cyclopts CLI provides a human check command and interactive
bootstrap. Doctor implements no daemon or background service.

## Current limits

- Declared probe failures/timeouts become logged_out; a timed-out daemon thread
  is not cancelled. This state does not prove observed logout.
- detect_auth leaves login_cmd=None.
- detect_git_identity can propagate axm-config import/get errors; env_doctor
  constructs auth/config outside its try block and can propagate them directly.
- Strict includes optional missing secrets and ignores config and undetermined
  auth. Its success is not a complete session-readiness guarantee.
- Non-TTY bootstrap skips installs but can still print/read a secrets prompt;
  confirmed provisioning then refuses without TTY.
- Bootstrap can exit 0 after printed install/provision failures. It does not
  log in, repair git configuration or roll back changes.
- Structured missing rows preserve accounts; setup hints, CLI secret labels
  and still_missing strings omit them.
- Custom install plans are not limited to registry commands or URLs.
  HTTPS/status/size checks are not signature verification.

These boundaries describe current behavior rather than future intentions.

## Documentation topology

The package's [explicit API page](../reference/api.md) is built independently.
The workspace generator also emits module pages under reference/axm_doctor/;
it never generated the old package-local reference/api/ directory.
The README is the repository entry; docs/index.md is the site homepage.
