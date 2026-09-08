import { describe, expect, it } from "vitest";

import {
  capabilityLabel,
  enumLabel,
  fieldLabel,
  preflightCheckLabel,
  statusLabel,
} from "../presentation/labels";

describe("Chinese presentation label registry", () => {
  it("maps runtime statuses and enums without exposing raw codes as normal labels", () => {
    expect(statusLabel("connection", "ONLINE")).toBe("在线");
    expect(statusLabel("health", "HEALTHY")).toBe("健康");
    expect(statusLabel("compatibility", "COMPATIBLE")).toBe("兼容");
    expect(statusLabel("scheduling", "IDLE")).toBe("空闲");
    expect(statusLabel("resource", "AVAILABLE")).toBe("可用");
    expect(statusLabel("executionBinding", "READY")).toBe("就绪");
    expect(statusLabel("ai", "PASS")).toBe("通过");
    expect(enumLabel("browser", "CHROMIUM")).toBe("Chromium 浏览器");
    expect(enumLabel("browserAction", "goal_completed")).toBe("提议完成目标");
    expect(statusLabel("lifecycle", "NOT_A_REAL_STATE")).toBe("未知状态");
  });

  it("maps capabilities, preflight checks, and validation fields", () => {
    expect(capabilityLabel("AI_EXPLORATION")).toBe("AI 探索");
    expect(capabilityLabel("FORMAL_EXECUTION")).toBe("正式执行");
    expect(preflightCheckLabel("RUNNER_RESOURCE_IDENTITY")).toBe("正式执行资源");
    expect(fieldLabel("runner_resource_identity")).toBe("Runner 执行资源");
  });
});
