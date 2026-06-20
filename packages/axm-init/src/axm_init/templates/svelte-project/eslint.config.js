// Flat ESLint config for SvelteKit (ESLint 9+). The svelte plugin handles
// .svelte files; sonarjs enforces the AXM complexity thresholds (cc<10/cog<15).
// Type-checking inside .svelte and a11y are handled by svelte-check, not here.
import svelte from "eslint-plugin-svelte";
import sonarjs from "eslint-plugin-sonarjs";

export default [
  ...svelte.configs["flat/recommended"],
  {
    files: ["src/**/*.ts", "src/**/*.svelte"],
    plugins: { sonarjs },
    rules: {
      complexity: ["error", 10],
      "sonarjs/cognitive-complexity": ["error", 15],
    },
  },
];
