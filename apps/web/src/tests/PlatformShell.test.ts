import { render, screen } from "@testing-library/vue";
import { ElCard, ElTag } from "element-plus";

import PlatformShell from "../components/PlatformShell.vue";

describe("PlatformShell", () => {
  it("renders the current R4.2 implementation-ready status", () => {
    render(PlatformShell, { global: { components: { ElCard, ElTag } } });

    expect(screen.getByText("AI 自动化测试执行平台")).toBeTruthy();
    expect(screen.getByText("P1 实施准备")).toBeTruthy();
    expect(screen.getByText("PDBR-2026.08.07-R4.2")).toBeTruthy();
    expect(screen.getByText("PASS（R4.2 基线证据）")).toBeTruthy();
    expect(screen.getByText("NOT_COMPLETED")).toBeTruthy();
  });
});
