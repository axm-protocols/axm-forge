# axm-ingot

Shared Python helpers with **zero runtime dependencies**. Use them for uv
workspace discovery, compact text, duration formatting, console-script lookup
and pytest outcome tallies. Python 3.12+ is required.

This package registers no CLI and no `axm.tools` entry point. Import its
functions directly. Workspace, suite and console helpers read the filesystem;
they do not write files or launch processes.

| Need | Start here |
|---|---|
| Learn with a disposable workspace | [Getting started](tutorials/getting-started.md) |
| Locate projects and workspace members | [Workspace recipes](howto/index.md) |
| Replace a local text renderer | [Renderer migration](how-to/migrate-local-render-to-ingot.md) |
| Find a helper and its import path | [API reference](reference/api.md) |
| Understand the dependency boundary | [Architecture](explanation/architecture.md) |
| Move shared code into this package | [Promote a helper](howto/promote-a-helper.md) |

## Install and try

```bash
uv add axm-ingot
```

```python
from axm_ingot import format_duration, header, tally_outcomes

counts = tally_outcomes(["FAILED tests/test_a.py", "SKIPPED tests/test_b.py"])
text = header("check", f"{counts['failed']} failed in {format_duration(1500)}")
assert text == "check | 1 failed in 1.5s"
```

The [README](https://github.com/axm-protocols/axm-forge/tree/main/packages/axm-ingot)
is the repository entry point; this page is the documentation home.

## Contracts to keep in mind

- Workspace members use directory basenames, which need not be unique or match
  distribution names.
- Rendered text is for people. It is not an escaped, reversible serialization.
- Defensive behavior is function-specific. There is no package-wide guarantee
  that arbitrary inputs cannot raise.
