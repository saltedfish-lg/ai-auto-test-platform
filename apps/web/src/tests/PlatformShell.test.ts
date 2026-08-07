import { render, screen } from "@testing-library/vue";
import { ElCard, ElTag } from "element-plus";

import PlatformShell from "../components/PlatformShell.vue";

describe("PlatformShell", () => {
  it("renders only the P0 engineering startup statement", () => {
    render(PlatformShell, { global: { components: { ElCard, ElTag } } });

    expect(screen.getByText("AI 自动化测试执行平台")).toBeTruthy();
    expect(screen.getByText("P0 工程底座")).toBeTruthy();
    expect(screen.getByText("PDBR-2026.08.06-R4.1")).toBeTruthy();
    expect(screen.getAllByText("NOT_EXECUTED")).toHaveLength(2);
  });
});
