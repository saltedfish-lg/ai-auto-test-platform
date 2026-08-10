import { describe, expect, it } from "vitest";

import { normalizeApiBaseUrl } from "../config";

describe("API base URL normalization", () => {
  it.each([
    ["", ""],
    ["/", ""],
    ["/gateway/", "/gateway"],
    ["https://api.example.test/", "https://api.example.test"],
  ])("normalizes %s without creating a double slash", (input, expected) => {
    expect(normalizeApiBaseUrl(input)).toBe(expected);
  });
});
