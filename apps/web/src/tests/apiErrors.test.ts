import { describe, expect, it } from "vitest";

import {
  ApiRequestError,
  getApiErrorMessage,
  getProblemCode,
} from "../api/errors";

describe("API error presentation", () => {
  it("maps validation fields to Chinese business names without exposing backend English detail", () => {
    const error = new ApiRequestError(422, "Request validation failed", {
      type: "urn:problem:validation",
      title: "Request validation failed",
      status: 422,
      code: "AUTH_REQUEST_VALIDATION_FAILED",
      detail: "Runner resource identity must be present.",
      correlation_id: "corr-validation",
      field_errors: [
        { field: "runner_resource_identity", message: "Field validation failed." },
      ],
    });

    expect(getApiErrorMessage(error, "执行预检查失败。")).toBe(
      "请检查以下字段：Runner 执行资源。",
    );
    expect(getApiErrorMessage(error, "执行预检查失败。")).not.toContain("identity");
    expect(getProblemCode(error)).toBe("AUTH_REQUEST_VALIDATION_FAILED");
  });

  it("falls back to a Chinese caller message instead of raw backend detail", () => {
    const error = new ApiRequestError(500, "server error", {
      type: "about:blank",
      title: "Internal error",
      status: 500,
      code: "INTERNAL_ERROR",
      detail: "Internal runtime implementation detail.",
      correlation_id: "corr-internal",
    });
    expect(getApiErrorMessage(error, "请求失败，请稍后重试。")).toBe("请求失败，请稍后重试。");
  });
});
