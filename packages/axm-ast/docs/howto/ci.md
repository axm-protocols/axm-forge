# Use in CI

All `axm-ast` commands support `--json` for machine-readable output, making them easy to integrate into CI pipelines.

## Gate on Impact Score

Fail CI if a change has HIGH impact without corresponding test updates:

```yaml
# .github/workflows/impact-check.yml
- name: Check impact
  run: |
    SCORE=$(axm-ast impact src/mylib --symbol "$CHANGED_SYMBOL" --json | jq -r '.score')
    if [ "$SCORE" = "HIGH" ]; then
      echo "⚠️ HIGH impact change — verify all affected tests pass"
      axm-ast impact src/mylib --symbol "$CHANGED_SYMBOL"
    fi
```

## Generate Context for LLM Prompts

Pipe project context directly into an LLM:

```bash
axm-ast context src/mylib --json > context.json
```

Or use compressed describe for smaller context windows:

```bash
axm-ast describe src/mylib --compress > codebase.txt
```

## Architecture Documentation

Auto-generate a Mermaid dependency graph:

```bash
axm-ast graph src/mylib --format mermaid > docs/dependency-graph.md
```

## Search for API Surface

Find all functions returning a specific type:

```bash
axm-ast search src/mylib --returns "PackageInfo" --json
```
