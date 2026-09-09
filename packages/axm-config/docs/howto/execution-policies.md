# Manage execution policies

The Python helpers store one exact ticket type's override. They do not run a
ticket or select a backend on behalf of the caller.

## Replace a policy

```python
import os
from axm_config import (
    delete_execution_policy, get_execution_policy,
    list_execution_policies, set_execution_policy,
)

os.environ["AXM_PROFILE"] = "docs-policy"
set_execution_policy(
    "dev.work", backend="codex", model="example-model", analysis_enabled=False
)
policy = get_execution_policy("dev.work")
assert policy.backend == "codex"
assert policy.analysis_enabled is False
assert "dev.work" in list_execution_policies()
delete_execution_policy("dev.work")
assert get_execution_policy("dev.work").backend is None
```

The backend and model must be supplied together as nonblank strings; their names
are not checked against a provider registry. `analysis_enabled` accepts a bool
in arguments and persisted data; strings are accepted only in the environment.
The result is the frozen, strict Pydantic `ExecutionPolicyOverride` with optional
`backend`, `model` and `analysis_enabled` fields.

`set_execution_policy` **replaces the whole policy**, not a partial merge.
Passing only `analysis_enabled=False` removes any persisted backend/model pair.
Passing no values, or calling `delete_execution_policy`, writes a v1 tombstone
to prevent an older policy from resurfacing. Neither removes environment overrides.

## Environment overrides and canonical persistence

Ticket types allow lowercase alphanumeric runs joined by single underscores
and dots, for example `research.paper_note`. Canonical storage encodes the
UTF-8 ticket type as lowercase hexadecimal:

```toml
[execution.v1.6465762e776f726b]
backend = "codex"
model = "example-model"
analysis_enabled = false
```

For `dev.work`, the actual environment variables are:

```bash
AXM_EXECUTION__V1__6465762E776F726B_BACKEND=codex \
AXM_EXECUTION__V1__6465762E776F726B_MODEL=example-model \
AXM_EXECUTION__V1__6465762E776F726B_ANALYSIS_ENABLED=false \
python -c 'from axm_config import get_execution_policy; print(get_execution_policy("dev.work"))'
```

The old `AXM_EXECUTION__DEV__WORK_*` variables are not read by the typed helper.
Backend/model resolve as one layer: supplying just one environment variable
raises `ConfigError`, even if the other field exists in the file.
Analysis resolves independently. Boolean strings accept
`true/1/yes/on` and `false/0/no/off` case-insensitively; surrounding whitespace
is rejected.

## Compatibility and enumeration

A canonical policy wins over the compatible `execution.<ticket_type>` file
section. A canonical `tombstone = "v1"` masks the legacy policy. New writes
use only the canonical namespace; legacy sections may remain on disk.

`get_execution_policy` validates the selected policy and raises `ConfigError`
for malformed values. It does not inherit policies from parent ticket types.
`list_execution_policies()` returns valid persisted policies in lexical order,
skips malformed leaves and tombstones, and does not apply or enumerate
environment-only policies.

Use the typed helpers to maintain the pair and tombstone contract. Generic
`set_` or `axm-config set` can create malformed policy data; there is no
dedicated execution-policy CLI or AXMTool in this package.
