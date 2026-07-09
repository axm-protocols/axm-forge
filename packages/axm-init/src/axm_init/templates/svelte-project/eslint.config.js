// Flat ESLint config for SvelteKit (ESLint 9+). The svelte plugin handles
// .svelte files; the rest mirrors the AXM practice + import-hygiene invariants
// (complexity, no-empty-catch, no-sync, jsdoc, no-internal-modules) so
// axm-audit's QUALITY_LINT picks them up. Type-checking inside .svelte and a11y
// are handled by svelte-check, not here.
import svelte from "eslint-plugin-svelte";
import sonarjs from "eslint-plugin-sonarjs";
import tseslint from "typescript-eslint";
import n from "eslint-plugin-n";
import jsdoc from "eslint-plugin-jsdoc";
import importX from "eslint-plugin-import-x";

export default [
  ...svelte.configs.recommended,
  // TypeScript needs its own parser (espree can't read type annotations);
  // inside .svelte files the svelte parser delegates <script lang="ts"> to it.
  {
    files: ["src/**/*.ts"],
    languageOptions: { parser: tseslint.parser },
  },
  {
    files: ["src/**/*.svelte"],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    files: ["src/**/*.ts", "src/**/*.svelte"],
    plugins: { sonarjs, n, jsdoc, "import-x": importX },
    rules: {
      complexity: ["error", 10],
      "sonarjs/cognitive-complexity": ["error", 15],
      "no-empty": ["error", { allowEmptyCatch: false }],
      "no-useless-catch": "error",
      "n/no-sync": "error",
      "no-await-in-loop": "error",
      "jsdoc/require-jsdoc": [
        "warn",
        { publicOnly: true, require: { FunctionDeclaration: true } },
      ],
      "import-x/no-internal-modules": "warn",
    },
  },
];
