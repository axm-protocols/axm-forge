// Flat ESLint config (ESLint 9+). Mirrors the intent of the Python ruff
// preset: catch unused symbols, undefined references, and enforce a
// complexity ceiling (cc < 10, matching the Python C901 threshold).
export default [
  {
    files: ["src/**/*.ts", "tests/**/*.ts"],
    rules: {
      "no-unused-vars": "error",
      "no-undef": "error",
      complexity: ["error", 10],
    },
  },
];
