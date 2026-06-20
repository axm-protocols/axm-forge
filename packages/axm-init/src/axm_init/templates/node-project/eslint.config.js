// Flat ESLint config (ESLint 9+). Mirrors the intent of the Python ruff preset:
// catch unused symbols and undefined references, and enforce the SonarSource
// 2025 complexity thresholds AXM uses for Python too (cc < 10, cog < 15).
import sonarjs from "eslint-plugin-sonarjs";

export default [
  {
    files: ["src/**/*.ts", "tests/**/*.ts"],
    plugins: { sonarjs },
    rules: {
      "no-unused-vars": "error",
      "no-undef": "error",
      complexity: ["error", 10],
      "sonarjs/cognitive-complexity": ["error", 15],
    },
  },
];
