# Quick Start

Explore the source of axm-ast itself without executing the analyzed library.
You need Python 3.12+ and uv.

## Install and choose a target

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --package axm-ast
```

The remaining commands run from that workspace root. Their target is the
member project `packages/axm-ast`, which selects `src/axm_ast`.
For another project, replace both the target and symbol names.

## 1. Orient yourself

```bash
uv run axm-ast context packages/axm-ast --depth 1
uv run axm-ast describe packages/axm-ast --detail toc
```

Context identifies the layout and modules. TOC limits the description to a
module inventory rather than placing every source body in your context.

## 2. Find and read one definition

```bash
uv run axm-ast search packages/axm-ast --name analyze_package
uv run axm-ast inspect packages/axm-ast --symbol analyze_package --source
```

Search matches substrings; inspect resolves exact definitions.
The inspected body shows src-layout selection and file discovery.
For ambiguous names, use the module-qualified candidate reported by inspect.

## 3. Explore dependencies

```bash
uv run axm-ast graph packages/axm-ast --format mermaid
uv run axm-ast callers packages/axm-ast --symbol analyze_package
uv run axm-ast flows packages/axm-ast --trace analyze_package --max-depth 1
```

A graph represents imports; callers and flows represent syntactic call sites.
None of these runs the target program. A limited flow can be truncated and
does not prove the complete runtime execution path.

## 4. Prepare a change review

```bash
uv run axm-ast impact packages/axm-ast --symbol analyze_package --precise-callers --json
uv run axm-ast docs packages/axm-ast --detail toc
```

Inspect the impact definition, caller locations and suggested tests. Scores
are configurable triage signals, not evidence that all affected tests were
found. The docs inventory tells you which pages to review alongside source.

## Next steps

- [Describe with filters and budgets](../howto/describe.md)
- [Analyze change impact](../howto/impact.md)
- [Choose scope and language](../howto/scope-and-languages.md)
- [Use tools via MCP](../howto/mcp.md)
- [Python API](../reference/api.md)

The dedicated CLI and AXM tools share analysis engines but not every default
or payload shape. See the [tool reference](../reference/tools.md).
