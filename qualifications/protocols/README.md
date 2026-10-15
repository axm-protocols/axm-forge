# Real shared-ticket interoperability qualification

This proof is deliberately outside Forge's standard pytest testpaths.
The autonomous axm-init unit/integration suite checks static generation,
resolution, readiness and registration. This separate qualification
creates its files through the public InitScaffoldTool.execute API and
imports the generated factory in an explicitly selected protocols Python
environment. It uses the real public protocols_core.TicketTypeDef, not a
mock, substitute module, or skipped capability.

Provide AXM_PROTOCOLS_PYTHON, or create a temporary local runtime.toml next
to the test with a `python` string containing the absolute virtualenv
interpreter path. Do not resolve the interpreter symlink: Python needs
the virtualenv invocation path. The test fails if the declaration,
interpreter, package, public type, context model, entry graph or unique
shared factory identity is missing or incompatible.

Run the public audit_test tool with the Forge workspace path and the
absolute file `qualifications/protocols/test_shared_unit_ticket.py`.
The tool has no per-call environment option; runtime.toml is the explicit
temporary configuration seam for that invocation. Remove only the file
you created afterwards. Never commit a local interpreter path.

Qualification measured on 2026-10-05:

- 1 passed, 1 collected, no skip, through MCP audit_test.
- protocols workspace dev commit
  `e5c20342ca32d09c3ff53d2120ac82ae6cd004dd`, clean at qualification.
- Interpreter:
  `/Users/gabriel/Documents/Code/python/axm-workspaces/axm-protocols/.venv/bin/python`.
- Generated type `ml.run`, actual shared `RunContext`, entry graph
  `ml.run.exec`; both `exec` and `inspect` import the identical factory.
- The temporary runtime.toml was created with overwrite disabled and
  removed after the run; no preexisting user configuration was replaced.

Limitation: this is a real measured local interoperability proof, not a
continuous CI guarantee. The PyPI protocols-core JSON endpoint returned
404 during this work. Once protocols-core is published with the required
public API, replace the external environment seam with a portable,
declared test-only qualification dependency. Do not add it to axm-init's
minimal runtime dependencies, do not silently import a sibling source
tree, and do not count a skip as an interoperability proof.
