import { test, expect } from "vitest";
import { greet } from "./index.js";

test("greet returns a greeting", () => {
  expect(greet("world")).toBe("Hello, world!");
});
