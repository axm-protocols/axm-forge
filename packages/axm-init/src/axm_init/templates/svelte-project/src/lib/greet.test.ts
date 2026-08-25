import { test, expect } from "vitest";
import { greet } from "./greet.js";

test("greet returns a greeting", () => {
  expect(greet("world")).toBe("Hello, world!");
});
