# Scaffold a Node or Svelte project

Use `--framework node` or `--framework svelte` for a **standalone** project:

```bash
axm init_scaffold my-service --framework node \
  --org myorg --author "Your Name" --email "you@example.com"

axm init_scaffold my-app --framework svelte \
  --org myorg --author "Your Name" --email "you@example.com"
```

These templates declare Node ≥20, TypeScript, ESLint and Vitest. Svelte uses
SvelteKit/Vite. Install the generated package's npm dependencies before using
its scripts; the Node template does not run `npm install` for you.

The Node template provides `npm run typecheck` with tsc; Svelte provides
`npm run check` with svelte-check. The generated package.json is the authority
for the full script set.

## Supported combinations

Only standalone Node/Svelte templates are registered. There is no Node/Svelte
workspace template; requesting one fails. The current member path uses the
Python template regardless of `framework`, so do not use it to create a
Node/Svelte member. Paper and experiment branches also use Python-side research
templates. See the [template matrix](../reference/templates.md).

`init_check` detects the framework from the target files; it has no
`--framework` override.
