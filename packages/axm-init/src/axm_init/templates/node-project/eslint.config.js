// Flat ESLint config (ESLint 9+). Mirrors the intent of the Python ruff/audit
// preset: unused/undefined symbols, SonarSource 2025 complexity (cc<10, cog<15),
// plus the practice + import-hygiene invariants AXM enforces in Python — here
// delegated to their community ESLint equivalents (idiomatic node: quality lives
// in the lint config, picked up by axm-audit's QUALITY_LINT).
import sonarjs from "eslint-plugin-sonarjs";
import n from "eslint-plugin-n";
import jsdoc from "eslint-plugin-jsdoc";
import importX from "eslint-plugin-import-x";

export default [
  {
    files: ["src/**/*.ts", "tests/**/*.ts"],
    plugins: { sonarjs, n, jsdoc, "import-x": importX },
    rules: {
      // Core hygiene (ruff E/F equivalents).
      "no-unused-vars": "error",
      "no-undef": "error",

      // Complexity — SonarSource 2025 thresholds (= AXM Python).
      complexity: ["error", 10],
      "sonarjs/cognitive-complexity": ["error", 15],

      // PRACTICE_BARE_EXCEPT: never swallow an error in an empty/useless catch.
      "no-empty": ["error", { allowEmptyCatch: false }],
      "no-useless-catch": "error",

      // PRACTICE_BLOCKING_IO: no sync I/O / no await-in-loop (n/no-sync is the
      // maintained successor to the deprecated core no-sync).
      "n/no-sync": "error",
      "no-await-in-loop": "error",

      // PRACTICE_DOCSTRING: TSDoc/JSDoc on public functions (the core
      // require-jsdoc was removed in ESLint 9 — use eslint-plugin-jsdoc).
      "jsdoc/require-jsdoc": [
        "warn",
        { publicOnly: true, require: { FunctionDeclaration: true } },
      ],

      // TEST_QUALITY_PRIVATE_IMPORTS: reach the public API, not internal
      // sub-paths of another package (the package.json "exports" field seals
      // the rest).
      "import-x/no-internal-modules": "warn",
    },
  },
];
