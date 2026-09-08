const DOMAIN_LABELS: Record<string, Record<string, string>> = {
  lifecycle: {
    CREATED: "已创建",
    DRAFT: "草稿",
    CONFIGURING: "配置中",
    VALIDATING: "验证中",
    ACTIVE: "已启用",
    LOCKED: "已锁定",
    INITIALIZED: "已初始化",
    DEGRADED: "降级",
    UNAVAILABLE: "不可用",
    CREDENTIAL_EXPIRED: "凭据已过期",
    CLEANUP_PENDING: "等待清理",
    DISABLED: "已停用",
    RECOVERING: "恢复中",
    RECOVERED: "已恢复",
    UNREACHABLE: "无法访问",
    ARCHIVED: "已归档",
    LOGICALLY_DELETED: "已逻辑删除",
    PUBLISHED: "已发布",
    SUPERSEDED: "已被取代",
    RETIRED: "已退役",
    REGISTERED: "已注册",
  },
  connection: {
    OFFLINE: "离线",
    CONNECTING: "连接中",
    ONLINE: "在线",
    LOST: "连接丢失",
  },
  health: {
    UNKNOWN: "未知",
    HEALTHY: "健康",
    DEGRADED: "降级",
    UNHEALTHY: "异常",
  },
  enablement: { ENABLED: "已启用", DISABLED: "已停用" },
  accessibility: { UNKNOWN: "未检测", REACHABLE: "可访问", UNREACHABLE: "无法访问" },
  credential: { VALID: "有效", EXPIRING: "即将过期", EXPIRED: "已过期", REVOKED: "已撤销" },
  terminalType: { MANAGEMENT: "管理端", CLIENT: "客户端", PDA: "PDA" },
  captchaPolicy: { NONE: "无需验证码", RESPONSE_HEADER: "响应头验证码" },
  binding: { BOUND: "已绑定", UNBOUND: "未绑定" },
  scheduling: {
    UNSCHEDULABLE: "不可调度",
    IDLE: "空闲",
    PARTIALLY_OCCUPIED: "部分占用",
    BUSY: "忙碌",
    DRAINING: "排空中",
  },
  resource: {
    AVAILABLE: "可用",
    PARTIALLY_OCCUPIED: "部分占用",
    EXHAUSTED: "已耗尽",
    RECLAIMING: "回收中",
    OCCUPIED: "已占用",
    UNAVAILABLE: "不可用",
  },
  compatibility: {
    UNKNOWN: "未判定",
    COMPATIBLE: "兼容",
    INCOMPATIBLE: "不兼容",
    UPGRADE_REQUIRED: "需要升级",
  },
  capabilityAvailability: {
    CONFIGURED: "已配置",
    NOT_CONFIGURED: "未配置",
  },
  capabilityValidation: {
    VALID: "已验证",
    INVALID: "验证失败",
    PENDING: "待验证",
  },
  executionBinding: {
    READY: "就绪",
    IN_USE: "使用中",
    RELEASED: "已释放",
    EXPIRED: "已过期",
  },
  lease: {
    ACTIVE: "生效中",
    EXPIRED: "已过期",
    FENCED: "已隔离",
    RELEASED: "已释放",
  },
  ai: {
    CREATED: "已创建",
    PLANNING: "规划中",
    READY: "就绪",
    RUNNING: "执行中",
    SUCCEEDED: "成功",
    SUCCESS: "成功",
    FAILED: "失败",
    FAIL: "未通过",
    PASS: "通过",
    CANCELLED: "已取消",
  },
  aiStep: {
    DECIDING: "决策中",
    EXECUTING: "执行中",
    SUCCEEDED: "成功",
    FAILED: "失败",
    COMPLETION_PROPOSED: "已提议完成",
    DISCARDED: "已丢弃",
  },
  browser: {
    CHROMIUM: "Chromium 浏览器",
    CHROME: "Google Chrome",
    EDGE: "Microsoft Edge",
  },
  artifact: {
    SCREENSHOT: "截图",
    VIDEO: "视频",
    TRACE: "Trace 跟踪",
  },
  network: {
    INTERNET: "公网",
    INTRANET: "内网",
    PROXY: "代理网络",
  },
  retry: { UNIFIED_OWNER: "统一执行所有者" },
  serialExecution: { SINGLE_PROCESS_UNIFIED_RETRY: "单进程统一重试" },
  browserAction: {
    Navigate: "打开页面",
    Click: "点击",
    Fill: "填写",
    Select: "选择",
    Check: "勾选",
    Uncheck: "取消勾选",
    PressKey: "按键",
    WaitFor: "等待",
    Inspect: "检查页面",
    Read: "读取页面",
    Scroll: "滚动页面",
    goal_completed: "提议完成目标",
    DECIDING: "正在决策",
  },
};

const CAPABILITY_LABELS: Record<string, string> = {
  AI_EXPLORATION: "AI 探索",
  BROWSER_CHROMIUM: "Chromium 浏览器",
  CAPTURE_SCREENSHOT: "截图采集",
  CONTEXT_ISOLATION: "上下文隔离",
  FORMAL_EXECUTION: "正式执行",
  MODE_HEADLESS: "无头模式",
  TERMINAL_ADMIN_WEB: "管理端 Web",
  TERMINAL_CLIENT_WEB: "客户端 Web",
  TERMINAL_PDA_WEB: "PDA Web",
  AGENT_VERSION: "Runner Agent 版本",
  PLAYWRIGHT_VERSION: "Playwright 版本",
};

const PREFLIGHT_CHECK_LABELS: Record<string, string> = {
  PROJECT: "项目状态",
  ENVIRONMENT: "环境状态",
  BUSINESS_TERMINAL: "业务终端",
  TERMINAL_ACCESS_REVISION: "终端访问修订",
  TERMINAL_ACCESS: "终端访问修订",
  LOGIN_STRATEGY: "登录策略",
  TEST_ACCOUNT: "测试账号",
  ACCOUNT_MAPPING: "账号终端映射",
  CREDENTIAL_REVISION: "登录凭据",
  EXECUTION_ATTEMPT: "执行实例",
  RUNNER: "Runner 状态",
  RUNNER_RESOURCE_IDENTITY: "正式执行资源",
  RUNTIME_POLICY: "运行策略",
  RUNNER_CAPABILITIES: "Runner 能力",
  IDENTITY_LEASE: "账号占用",
  RUNNER_LEASE: "Runner 资源占用",
};

const FIELD_LABELS: Record<string, string> = {
  project_id: "项目",
  environment_id: "执行环境",
  business_terminal_id: "业务终端",
  test_account_id: "测试账号",
  runner_id: "Runner",
  runtime_policy_revision_id: "运行策略",
  execution_attempt_id: "执行实例",
  runner_resource_identity: "Runner 执行资源",
  owner_user_id: "首任负责人",
};

export function statusLabel(domain: string, value: string | null | undefined): string {
  if (!value) return "—";
  return DOMAIN_LABELS[domain]?.[value] ?? "未知状态";
}

export function enumLabel(domain: string, value: string | null | undefined): string {
  if (!value) return "—";
  return DOMAIN_LABELS[domain]?.[value] ?? "未知选项";
}

export function capabilityLabel(code: string | null | undefined): string {
  if (!code) return "未知能力";
  return CAPABILITY_LABELS[code] ?? "未知能力";
}

export function preflightCheckLabel(code: string): string {
  return PREFLIGHT_CHECK_LABELS[code] ?? "执行检查";
}

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? "提交字段";
}
