# 自动轮询与人工重跑 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为现有飞书生图工作流增加默认关闭的自动轮询模式，并确保已完成任务不会被自动重复执行；同时提供一个必须显式确认的人工重跑入口。

**Architecture:** 保持 `TaskRunner` 负责“一次批处理”，把模式选择、轮询调度、人工重跑放在 `runner` 和独立的小服务里。自动轮询只处理 `待处理` 与 `失败待重试`，已完成任务的重跑只能通过单独命令和确认参数触发。

**Tech Stack:** TypeScript、Vitest、Zod、现有 Feishu Bitable REST API 适配层、tsx CLI

---

## 文件结构与职责

- 修改 `src/config.ts`
  负责新增 `AUTO_RUN_ENABLED`、`AUTO_RUN_INTERVAL_MINUTES` 配置解析。
- 修改 `src/runner.ts`
  负责解析 CLI 模式，支持 `run-once`、`run-loop`、`rerun-task`。
- 新建 `src/services/task-loop-runner.ts`
  负责轮询调度、进程内防重叠执行。
- 修改 `src/adapters/feishu.ts`
  负责按 `task_id` 查询任务、把已完成任务安全重置回可执行状态。
- 修改 `src/types.ts`
  负责补充轮询模式或人工重跑需要的任务结构与状态类型复用。
- 修改 `tests/config.test.ts`
  覆盖新环境变量的默认值与解析。
- 修改 `tests/runner.test.ts`
  覆盖模式选择与参数传递。
- 新建 `tests/task-loop-runner.test.ts`
  覆盖轮询逻辑与重叠保护。
- 修改 `tests/feishu-adapter.test.ts`
  覆盖按 `task_id` 查询与重跑重置。
- 修改 `tests/e2e-smoke.test.ts`
  覆盖人工重跑入口或单次执行主路径不回归。
- 修改 `.env.example`
  补充自动轮询配置示例。
- 修改 `README.md`
  补充运行模式说明与人工重跑命令说明。

### Task 1: 增加自动轮询配置

**Files:**
- Modify: `src/config.ts`
- Test: `tests/config.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
it("loads auto-run config with safe defaults", () => {
  const config = loadConfig({
    FEISHU_APP_ID: "app-id",
    FEISHU_APP_SECRET: "app-secret",
    FEISHU_APP_TOKEN: "app-token",
    FEISHU_TABLE_ID: "table-id",
    FEISHU_BOT_WEBHOOK: "https://example.com/hook",
    OUTPUT_DIR: "./data",
    RETENTION_DAYS: "7",
  });

  expect(config.autoRunEnabled).toBe(false);
  expect(config.autoRunIntervalMinutes).toBe(10);
});

it("loads explicit auto-run config overrides", () => {
  const config = loadConfig({
    FEISHU_APP_ID: "app-id",
    FEISHU_APP_SECRET: "app-secret",
    FEISHU_APP_TOKEN: "app-token",
    FEISHU_TABLE_ID: "table-id",
    FEISHU_BOT_WEBHOOK: "https://example.com/hook",
    OUTPUT_DIR: "./data",
    RETENTION_DAYS: "7",
    AUTO_RUN_ENABLED: "true",
    AUTO_RUN_INTERVAL_MINUTES: "3",
  });

  expect(config.autoRunEnabled).toBe(true);
  expect(config.autoRunIntervalMinutes).toBe(3);
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/config.test.ts`
Expected: FAIL，因为 `autoRunEnabled` 和 `autoRunIntervalMinutes` 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
const schema = z.object({
  FEISHU_APP_ID: z.string().min(1),
  FEISHU_APP_SECRET: z.string().min(1),
  FEISHU_APP_TOKEN: z.string().min(1),
  FEISHU_TABLE_ID: z.string().min(1),
  FEISHU_BOT_WEBHOOK: z.string().url(),
  OUTPUT_DIR: z.string().min(1),
  RETENTION_DAYS: z.coerce.number().int().positive(),
  AUTO_RUN_ENABLED: z.coerce.boolean().default(false),
  AUTO_RUN_INTERVAL_MINUTES: z.coerce.number().int().positive().default(10),
  IMAGE_PROVIDER: z.enum(["mock", "openai"]).default("mock"),
  OPENAI_API_KEY: z.string().optional(),
  OPENAI_BASE_URL: z.string().url().optional(),
  OPENAI_IMAGE_MODEL: z.string().min(1).default("gpt-image-1"),
});

export type AppConfig = {
  feishuAppId: string;
  feishuAppSecret: string;
  feishuAppToken: string;
  feishuTableId: string;
  feishuBotWebhook: string;
  outputDir: string;
  retentionDays: number;
  autoRunEnabled: boolean;
  autoRunIntervalMinutes: number;
  imageProvider: "mock" | "openai";
  openaiApiKey?: string;
  openaiBaseUrl?: string;
  openaiImageModel: string;
};

const parsed = schema.parse({
  FEISHU_APP_ID: env.FEISHU_APP_ID,
  FEISHU_APP_SECRET: env.FEISHU_APP_SECRET,
  FEISHU_APP_TOKEN: env.FEISHU_APP_TOKEN,
  FEISHU_TABLE_ID: env.FEISHU_TABLE_ID,
  FEISHU_BOT_WEBHOOK: env.FEISHU_BOT_WEBHOOK,
  OUTPUT_DIR: env.OUTPUT_DIR,
  RETENTION_DAYS: env.RETENTION_DAYS,
  AUTO_RUN_ENABLED: env.AUTO_RUN_ENABLED,
  AUTO_RUN_INTERVAL_MINUTES: env.AUTO_RUN_INTERVAL_MINUTES,
  IMAGE_PROVIDER: env.IMAGE_PROVIDER,
  OPENAI_API_KEY: env.OPENAI_API_KEY,
  OPENAI_BASE_URL: env.OPENAI_BASE_URL,
  OPENAI_IMAGE_MODEL: env.OPENAI_IMAGE_MODEL,
});

return {
  feishuAppId: parsed.FEISHU_APP_ID,
  feishuAppSecret: parsed.FEISHU_APP_SECRET,
  feishuAppToken: parsed.FEISHU_APP_TOKEN,
  feishuTableId: parsed.FEISHU_TABLE_ID,
  feishuBotWebhook: parsed.FEISHU_BOT_WEBHOOK,
  outputDir: path.resolve(parsed.OUTPUT_DIR),
  retentionDays: parsed.RETENTION_DAYS,
  autoRunEnabled: parsed.AUTO_RUN_ENABLED,
  autoRunIntervalMinutes: parsed.AUTO_RUN_INTERVAL_MINUTES,
  imageProvider: parsed.IMAGE_PROVIDER,
  openaiApiKey: parsed.OPENAI_API_KEY,
  openaiBaseUrl: parsed.OPENAI_BASE_URL,
  openaiImageModel: parsed.OPENAI_IMAGE_MODEL,
};
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/config.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/config.test.ts src/config.ts
git commit -m "feat: add auto-run config flags"
```

### Task 2: 增加轮询执行器与防重叠保护

**Files:**
- Create: `src/services/task-loop-runner.ts`
- Modify: `tests/runner.test.ts`
- Create: `tests/task-loop-runner.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { describe, expect, it, vi } from "vitest";
import { TaskLoopRunner } from "../src/services/task-loop-runner";

describe("TaskLoopRunner", () => {
  it("runs one poll immediately and skips overlapping polls", async () => {
    let release!: () => void;
    const firstRun = new Promise<void>((resolve) => {
      release = resolve;
    });
    const runBatch = vi
      .fn()
      .mockReturnValueOnce(firstRun)
      .mockResolvedValueOnce(undefined);

    const sleeper = vi.fn().mockResolvedValue(undefined);
    const loop = new TaskLoopRunner(runBatch, 1, sleeper);

    const firstTick = loop.tick();
    const secondTick = loop.tick();

    expect(runBatch).toHaveBeenCalledTimes(1);

    release();
    await firstTick;
    await secondTick;
  });
});
```

```ts
it("refuses loop mode when AUTO_RUN_ENABLED is false", async () => {
  await expect(
    createRunner(
      {
        IMAGE_PROVIDER: "mock",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
        AUTO_RUN_ENABLED: "false",
      },
      {
        buildTaskRunner: () => ({ runOnce: vi.fn() }) as any,
      },
    )("run-loop" as never),
  ).rejects.toThrow("AUTO_RUN_ENABLED is false");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/task-loop-runner.test.ts tests/runner.test.ts`
Expected: FAIL，因为 `TaskLoopRunner` 和 loop mode 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
export class TaskLoopRunner {
  private running = false;

  constructor(
    private readonly runBatch: () => Promise<void>,
    private readonly intervalMinutes: number,
    private readonly sleep: (ms: number) => Promise<void> = (ms) =>
      new Promise((resolve) => setTimeout(resolve, ms)),
  ) {}

  async tick(): Promise<void> {
    if (this.running) {
      return;
    }

    this.running = true;
    try {
      await this.runBatch();
    } finally {
      this.running = false;
    }
  }

  async runForever(): Promise<void> {
    await this.tick();
    for (;;) {
      await this.sleep(this.intervalMinutes * 60 * 1000);
      await this.tick();
    }
  }
}
```

```ts
type RunnerMode = "run-once" | "run-loop" | "seed-task" | "rerun-task";

export function createRunner(
  env: Record<string, string | undefined> = process.env,
  deps: RunnerDeps = {},
) {
  return async function run(mode: RunnerMode = "run-once"): Promise<void> {
    const config = loadConfig(env);
    const imageProvider = config.imageProvider === "openai"
      ? new OpenAiImageProvider(
          config.openaiApiKey ?? "",
          config.openaiBaseUrl,
          config.openaiImageModel,
        )
      : new MockImageProvider();

    const taskRunner =
      deps.buildTaskRunner?.(config, imageProvider) ??
      new TaskRunner(
        new FeishuAdapter({
          appId: config.feishuAppId,
          appSecret: config.feishuAppSecret,
          appToken: config.feishuAppToken,
          tableId: config.feishuTableId,
          webhook: config.feishuBotWebhook,
        }),
        imageProvider,
        new ArchiveService(config.outputDir),
      );

    if (mode === "run-loop") {
      if (!config.autoRunEnabled) {
        throw new Error("AUTO_RUN_ENABLED is false; loop mode is disabled.");
      }

      const loopRunner = new TaskLoopRunner(() => taskRunner.runOnce(), config.autoRunIntervalMinutes);
      await loopRunner.runForever();
      return;
    }

    await taskRunner.runOnce();
  };
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/task-loop-runner.test.ts tests/runner.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/task-loop-runner.test.ts tests/runner.test.ts src/services/task-loop-runner.ts src/runner.ts
git commit -m "feat: add safe auto-run loop mode"
```

### Task 3: 增加按 task_id 查询与已完成任务重置能力

**Files:**
- Modify: `src/adapters/feishu.ts`
- Modify: `tests/feishu-adapter.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
it("finds a task by task_id regardless of status", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tenant_access_token: "tenant-token",
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        data: {
          items: [
            {
              record_id: "rec-1",
              fields: {
                task_seq: 8,
                task_id: "iphone-pro-test",
                product_name: "iPhone Pro",
                owner_open_id: "ou_123",
                owner_display_name: "张三",
                prompt_template: "phone hero",
                image_count: 1,
                retry_count: 0,
                task_status: "已完成",
              },
            },
          ],
        },
      }),
    });

  const adapter = new FeishuAdapter(
    {
      appId: "app-id",
      appSecret: "secret",
      appToken: "token",
      tableId: "table-id",
      webhook: "https://example.com/webhook",
    },
    fetcher as typeof fetch,
  );

  const task = await adapter.findTaskByTaskId("iphone-pro-test");

  expect(task?.taskId).toBe("iphone-pro-test");
  expect(task?.status).toBe("已完成");
});

it("resets a completed task back to 待处理 for manual rerun", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        tenant_access_token: "tenant-token",
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true }),
    });

  const adapter = new FeishuAdapter(
    {
      appId: "app-id",
      appSecret: "secret",
      appToken: "token",
      tableId: "table-id",
      webhook: "https://example.com/webhook",
    },
    fetcher as typeof fetch,
  );

  await adapter.resetTaskForRerun("rec-1", "张三");

  const body = JSON.parse(
    String((fetcher.mock.calls[1]?.[1] as RequestInit | undefined)?.body),
  ) as { fields?: Record<string, unknown> };

  expect(body.fields).toMatchObject({
    task_status: "待处理",
    status_note: "",
    owner_display_name: "张三",
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/feishu-adapter.test.ts`
Expected: FAIL，因为 `findTaskByTaskId` 和 `resetTaskForRerun` 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
async findTaskByTaskId(taskId: string): Promise<ImageTask | null> {
  const tasks = await this.buildTaskItems();
  return tasks.find((task) => task.taskId === taskId) ?? null;
}

async resetTaskForRerun(
  recordId: string,
  ownerDisplayName: string,
): Promise<void> {
  const tenantAccessToken = await this.getTenantAccessToken();
  await this.requestJson(
    `https://open.feishu.cn/open-apis/bitable/v1/apps/${this.config.appToken}/tables/${this.config.tableId}/records/${recordId}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${tenantAccessToken}`,
      },
      body: JSON.stringify({
        fields: {
          task_status: "待处理",
          status_note: "",
          owner_display_name: ownerDisplayName,
        },
      }),
    },
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/feishu-adapter.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/feishu-adapter.test.ts src/adapters/feishu.ts
git commit -m "feat: add manual rerun task lookup"
```

### Task 4: 增加人工重跑命令与确认参数

**Files:**
- Modify: `src/runner.ts`
- Modify: `tests/runner.test.ts`
- Modify: `tests/e2e-smoke.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
it("refuses rerunning a completed task without confirmation", async () => {
  const adapter = {
    findTaskByTaskId: vi.fn().mockResolvedValue({
      recordId: "rec-1",
      taskSeq: 8,
      taskId: "iphone-pro-test",
      productName: "iPhone Pro",
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
      promptTemplate: "phone hero",
      imageCount: 1,
      retryCount: 0,
      status: "已完成",
    }),
  };

  await expect(
    createTaskRerunner(
      adapter as never,
      { confirmRerunCompleted: false },
      { runOnce: vi.fn() } as never,
    )("iphone-pro-test"),
  ).rejects.toThrow("requires confirmation");
});

it("resets and reruns a completed task after explicit confirmation", async () => {
  const adapter = {
    findTaskByTaskId: vi.fn().mockResolvedValue({
      recordId: "rec-1",
      taskSeq: 8,
      taskId: "iphone-pro-test",
      productName: "iPhone Pro",
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
      promptTemplate: "phone hero",
      imageCount: 1,
      retryCount: 0,
      status: "已完成",
    }),
    resetTaskForRerun: vi.fn().mockResolvedValue(undefined),
  };
  const runOnce = vi.fn().mockResolvedValue(undefined);

  await createTaskRerunner(
    adapter as never,
    { confirmRerunCompleted: true },
    { runOnce } as never,
  )("iphone-pro-test");

  expect(adapter.resetTaskForRerun).toHaveBeenCalledWith("rec-1", "张三");
  expect(runOnce).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/runner.test.ts tests/e2e-smoke.test.ts`
Expected: FAIL，因为人工重跑入口和确认逻辑还不存在。

- [ ] **Step 3: 写最小实现**

```ts
type RerunOptions = {
  confirmRerunCompleted: boolean;
};

export function createTaskRerunner(
  adapter: Pick<FeishuAdapter, "findTaskByTaskId" | "resetTaskForRerun">,
  options: RerunOptions,
  taskRunner: Pick<TaskRunner, "runOnce">,
) {
  return async function rerunTask(taskId: string): Promise<void> {
    const task = await adapter.findTaskByTaskId(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found.`);
    }

    if (task.status === "已完成" && !options.confirmRerunCompleted) {
      throw new Error(
        `Rerunning completed task ${taskId} requires confirmation.`,
      );
    }

    if (task.status === "已完成") {
      await adapter.resetTaskForRerun(task.recordId, task.ownerDisplayName);
    }

    await taskRunner.runOnce();
  };
}
```

```ts
if (mode === "rerun-task") {
  const taskId = process.argv[3];
  const confirmRerunCompleted = process.argv.includes("--confirm-rerun-completed");
  if (!taskId) {
    throw new Error("rerun-task requires a task_id argument.");
  }

  const adapter = new FeishuAdapter({
    appId: config.feishuAppId,
    appSecret: config.feishuAppSecret,
    appToken: config.feishuAppToken,
    tableId: config.feishuTableId,
    webhook: config.feishuBotWebhook,
  });

  const rerun = createTaskRerunner(
    adapter,
    { confirmRerunCompleted },
    taskRunner,
  );
  await rerun(taskId);
  return;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/runner.test.ts tests/e2e-smoke.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/runner.test.ts tests/e2e-smoke.test.ts src/runner.ts
git commit -m "feat: add confirmed manual rerun command"
```

### Task 5: 补充文档与全量验证

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: 写文档变更**

```dotenv
AUTO_RUN_ENABLED=false
AUTO_RUN_INTERVAL_MINUTES=10
```

```md
## 自动轮询

默认关闭：

```bash
AUTO_RUN_ENABLED=false
```

开启轮询：

```bash
AUTO_RUN_ENABLED=true
AUTO_RUN_INTERVAL_MINUTES=10
npm exec tsx src/runner.ts run-loop
```

人工重跑已完成任务：

```bash
npm exec tsx src/runner.ts rerun-task iphone-pro-test --confirm-rerun-completed
```
```

- [ ] **Step 2: 运行完整验证**

Run: `npm test -- tests/config.test.ts tests/runner.test.ts tests/task-loop-runner.test.ts tests/feishu-adapter.test.ts tests/task-runner.test.ts tests/e2e-smoke.test.ts`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add .env.example README.md tests/config.test.ts tests/runner.test.ts tests/task-loop-runner.test.ts tests/feishu-adapter.test.ts tests/task-runner.test.ts tests/e2e-smoke.test.ts src/config.ts src/runner.ts src/services/task-loop-runner.ts src/adapters/feishu.ts
git commit -m "docs: document auto-run and rerun workflow"
```
