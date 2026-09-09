# Load a consumer package's config

Define a Pydantic model for non-sensitive settings. Credentials belong in
axm-vault and should be resolved separately.

## Declare and load a model

The following Python program selects a named profile for this process and
persists a native integer. Use an unused profile name when trying it.

```python
import os
from pydantic import BaseModel
from axm_config import delete, get_file, load, set_

os.environ["AXM_PROFILE"] = "docs-consumer"

class ResearchConfig(BaseModel):
    dataset: str
    timeout: int = 30

set_("research.demo", "dataset", "sample")
set_("research.demo", "timeout", 45)
cfg = load("research.demo", ResearchConfig)
assert cfg.dataset == "sample"
assert cfg.timeout == 45
assert get_file("research.demo", "timeout") == 45

os.environ["AXM_RESEARCH__DEMO_TIMEOUT"] = "10"
assert load("research.demo", ResearchConfig).timeout == 10
assert get_file("research.demo", "timeout") == 45

del os.environ["AXM_RESEARCH__DEMO_TIMEOUT"]
delete("research.demo", "timeout")
assert load("research.demo", ResearchConfig).timeout == 30
delete("research.demo", "dataset")
```

`load(namespace, model)` resolves each **field name**, omits unresolved fields
and calls `model.model_validate`. Model defaults and default factories then
apply. Required missing fields and validation errors become `ConfigError`.
Pydantic performs conversions; `get` itself keeps environment values as strings.
Aliases are not used as configuration lookup keys.

## Diagnose an override

Run both commands with the same profile and environment as the consumer:

```bash
AXM_PROFILE=docs-consumer AXM_RESEARCH__DEMO_TIMEOUT=10 axm-config doctor research.demo
AXM_PROFILE=docs-consumer AXM_RESEARCH__DEMO_TIMEOUT=10 axm config_doctor --namespace research.demo
```

The report names the winning layer without returning the value.
It still parses the file internally and may create or chmod the AXM home.
Specify the namespace to discover environment-only settings.
