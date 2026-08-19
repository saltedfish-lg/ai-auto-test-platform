import { fireEvent, render, screen, waitFor } from "@testing-library/vue";
import ElementPlus from "element-plus";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../api/client";
import { ApiRequestError } from "../api/errors";
import type { ProjectResource } from "../generated/types";
import { useProjectsStore } from "../stores/projects";
import { useSessionStore } from "../stores/session";
import ProjectDetailView from "../views/ProjectDetailView.vue";
import ProjectsListView from "../views/ProjectsListView.vue";
import { authenticationResponse, currentUser, problemDetails } from "./auth-fixtures";

const project: ProjectResource = {
  project_id: "01JPROJECT00000000000000001",
  project_code: "ATP-DEMO",
  display_name: "自动化平台",
  lifecycle_status: "ACTIVE",
  row_version: 3,
  owners: [
    {
      user_id: "01JOWNER000000000000000001",
      display_name: "项目负责人",
      membership_status: "ACTIVE",
    },
  ],
  created_at: "2026-08-18T00:00:00Z",
  updated_at: "2026-08-18T00:00:00Z",
};

async function authenticatedPinia(permissions: string[]) {
  const pinia = createPinia();
  setActivePinia(pinia);
  vi.spyOn(apiClient, "login_platform_user").mockResolvedValue(
    authenticationResponse(currentUser({ permissions })),
  );
  await useSessionStore().login({ username: "admin", password: "input-only" });
  return pinia;
}

describe("项目管理页面（组件测试，API 为 mock）", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders the authorized project list and exposes create only with PROJECT_CREATE", async () => {
    const pinia = await authenticatedPinia(["PROJECT_VIEW", "PROJECT_CREATE"]);
    vi.spyOn(apiClient, "list_project").mockResolvedValue({
      items: [project],
      page: { page: 1, page_size: 20, total: 1 },
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects", name: "projects.list", component: ProjectsListView },
        { path: "/projects/:id", name: "projects.detail", component: ProjectDetailView },
      ],
    });
    await router.push("/projects");
    await router.isReady();

    render(ProjectsListView, { global: { plugins: [pinia, ElementPlus, router] } });

    expect(await screen.findByText("ATP-DEMO")).toBeTruthy();
    expect(screen.getByText("自动化平台")).toBeTruthy();
    expect(screen.getByText("项目负责人")).toBeTruthy();
    expect(screen.getByRole("button", { name: "创建项目" })).toBeTruthy();
  });

  it("hides create for a view-only identity and shows the operation-specific API error", async () => {
    const pinia = await authenticatedPinia(["PROJECT_VIEW"]);
    const failure = problemDetails(403, "AUTH_PERMISSION_DENIED");
    vi.spyOn(apiClient, "list_project").mockRejectedValue(
      new ApiRequestError(403, failure.title, failure),
    );
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/projects", component: ProjectsListView }],
    });
    await router.push("/projects");
    await router.isReady();

    render(ProjectsListView, { global: { plugins: [pinia, ElementPlus, router] } });

    expect(await screen.findByText("当前账号没有执行此操作的权限。")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "创建项目" })).toBeNull();
  });

  it("renders owner and lifecycle state, then persists an authorized edit", async () => {
    const pinia = await authenticatedPinia(["PROJECT_VIEW", "PROJECT_EDIT"]);
    vi.spyOn(apiClient, "get_project").mockResolvedValue({
      data: project,
      correlation_id: "project-detail-correlation",
    });
    const updated = { ...project, display_name: "自动化平台二期", row_version: 4 };
    const update = vi.spyOn(apiClient, "update_project").mockResolvedValue({
      data: updated,
      correlation_id: "project-update-correlation",
    });
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects", name: "projects.list", component: ProjectsListView },
        { path: "/projects/:id", name: "projects.detail", component: ProjectDetailView },
      ],
    });
    await router.push(`/projects/${project.project_id}`);
    await router.isReady();

    render(ProjectDetailView, { global: { plugins: [pinia, ElementPlus, router] } });

    expect(await screen.findByRole("heading", { name: "自动化平台" })).toBeTruthy();
    expect(screen.getAllByText("项目负责人").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("ACTIVE").length).toBeGreaterThanOrEqual(1);
    await fireEvent.click(screen.getByRole("button", { name: "编辑基础信息" }));
    await fireEvent.update(screen.getByLabelText("项目名称"), "自动化平台二期");
    await fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(update.mock.calls[0]?.[0]).toBe(project.project_id);
    expect(update.mock.calls[0]?.[1]).toMatchObject({
      expected_version: 3,
      display_name: "自动化平台二期",
    });
    expect(await screen.findByRole("heading", { name: "自动化平台二期" })).toBeTruthy();
  });

  it("clears project data after a failed reload and across an identity change", async () => {
    await authenticatedPinia(["PROJECT_VIEW"]);
    const projects = useProjectsStore();
    const session = useSessionStore();
    vi.spyOn(apiClient, "list_project").mockResolvedValue({
      items: [project],
      page: { page: 1, page_size: 20, total: 1 },
    });
    await projects.loadProjects();
    expect(projects.items).toEqual([project]);

    const failure = problemDetails(403, "AUTH_PERMISSION_DENIED");
    vi.mocked(apiClient.list_project).mockRejectedValueOnce(
      new ApiRequestError(403, failure.title, failure),
    );
    await expect(projects.loadProjects()).rejects.toBeInstanceOf(ApiRequestError);
    expect(projects.items).toEqual([]);

    vi.mocked(apiClient.login_platform_user).mockResolvedValueOnce(
      authenticationResponse(currentUser({ user_id: "01J00000000000000000000002" })),
    );
    projects.current = project;
    await session.login({ username: "other-user", password: "input-only" });
    expect(projects.current).toBeNull();
    expect(projects.items).toEqual([]);
  });

  it("reloads and replaces the current project when the detail route id changes", async () => {
    const pinia = await authenticatedPinia(["PROJECT_VIEW"]);
    const second = {
      ...project,
      project_id: "01JPROJECT00000000000000002",
      project_code: "ATP-NEXT",
      display_name: "第二个项目",
    };
    vi.spyOn(apiClient, "get_project").mockImplementation(async (projectId) => ({
      data: projectId === second.project_id ? second : project,
      correlation_id: `project-${projectId}`,
    }));
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/projects", name: "projects.list", component: ProjectsListView },
        { path: "/projects/:id", name: "projects.detail", component: ProjectDetailView },
      ],
    });
    await router.push(`/projects/${project.project_id}`);
    await router.isReady();
    render(ProjectDetailView, { global: { plugins: [pinia, ElementPlus, router] } });
    expect(await screen.findByRole("heading", { name: "自动化平台" })).toBeTruthy();

    await router.push(`/projects/${second.project_id}`);
    expect(await screen.findByRole("heading", { name: "第二个项目" })).toBeTruthy();
    expect(useProjectsStore().current?.project_id).toBe(second.project_id);
  });

  it("does not let an older detail response overwrite a newer route request", async () => {
    await authenticatedPinia(["PROJECT_VIEW"]);
    const projects = useProjectsStore();
    const second = {
      ...project,
      project_id: "01JPROJECT00000000000000003",
      project_code: "ATP-LATEST",
    };
    let resolveOlder!: (value: { data: ProjectResource; correlation_id: string }) => void;
    vi.spyOn(apiClient, "get_project")
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveOlder = resolve;
          }),
      )
      .mockResolvedValueOnce({ data: second, correlation_id: "latest-response" });

    const olderRequest = projects.loadProject(project.project_id);
    await projects.loadProject(second.project_id);
    resolveOlder({ data: project, correlation_id: "older-response" });
    await olderRequest;

    expect(projects.current?.project_id).toBe(second.project_id);
  });
});
