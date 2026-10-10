import { describe, expect, it, vi } from "vitest";
import {
  createErpReportRunner,
  createRunner,
  createTaskRerunner,
} from "../src/runner";

describe("createRunner", () => {
  it("wires the mock provider when IMAGE_PROVIDER=mock", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const runner = createRunner(
      {
        IMAGE_PROVIDER: "mock",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
      },
      {
        buildTaskRunner: () => ({ runOnce }) as any,
      },
    );

    await runner();

    expect(runOnce).toHaveBeenCalledTimes(1);
  });

  it("uses the openai provider when IMAGE_PROVIDER=openai", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const buildTaskRunner = vi.fn().mockReturnValue({ runOnce });

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "openai",
        OPENAI_API_KEY: "sk-test",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
      },
      {
        buildTaskRunner,
      },
    );

    await runner();

    expect(buildTaskRunner).toHaveBeenCalledOnce();
    expect(buildTaskRunner.mock.calls[0]?.[1]?.constructor?.name).toBe(
      "OpenAiImageProvider",
    );
    expect(runOnce).toHaveBeenCalledOnce();
  });

  it("passes the OpenAI-compatible base URL into the provider", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const buildTaskRunner = vi.fn().mockReturnValue({ runOnce });

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "openai",
        OPENAI_API_KEY: "sk-test",
        OPENAI_BASE_URL: "https://gateway.example.com/v1",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
      },
      {
        buildTaskRunner,
      },
    );

    await runner();

    expect((buildTaskRunner.mock.calls[0]?.[1] as any)?.baseURL).toBe(
      "https://gateway.example.com/v1",
    );
  });

  it("passes the configured image model into the provider", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const buildTaskRunner = vi.fn().mockReturnValue({ runOnce });

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "openai",
        OPENAI_API_KEY: "sk-test",
        OPENAI_IMAGE_MODEL: "gpt-image-2",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
      },
      {
        buildTaskRunner,
      },
    );

    await runner();

    expect((buildTaskRunner.mock.calls[0]?.[1] as any)?.model).toBe(
      "gpt-image-2",
    );
  });

  it("refuses loop mode when AUTO_RUN_ENABLED is false", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const runner = createRunner(
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
        buildTaskRunner: () => ({ runOnce }) as any,
      },
    );

    await expect(runner("run-loop")).rejects.toThrow(
      "AUTO_RUN_ENABLED is false",
    );
  });

  it("runs the loop runner when loop mode is enabled", async () => {
    const runOnce = vi.fn().mockResolvedValue(undefined);
    const runForever = vi.fn().mockResolvedValue(undefined);
    const buildTaskRunner = vi.fn().mockReturnValue({ runOnce });
    const buildTaskLoopRunner = vi.fn().mockReturnValue({ runForever });

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "mock",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "./data",
        RETENTION_DAYS: "7",
        AUTO_RUN_ENABLED: "true",
        AUTO_RUN_INTERVAL_MINUTES: "3",
      },
      {
        buildTaskRunner,
        buildTaskLoopRunner,
      } as any,
    );

    await runner("run-loop");

    expect(buildTaskLoopRunner).toHaveBeenCalledOnce();
    expect(runForever).toHaveBeenCalledOnce();
    expect(runOnce).not.toHaveBeenCalled();
  });

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
      resetTaskForRerun: vi.fn(),
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

  it("runs the mock ERP report mode and sends a report", async () => {
    const sendErpReport = vi.fn().mockResolvedValue(undefined);
    const runner = createErpReportRunner(
      {
        getDailyReport: vi.fn().mockResolvedValue({
          summary: {
            totalSales: 152340.5,
            totalOrders: 328,
            totalAdSpend: 28120.3,
            averageGrossMargin: 0.34,
          },
          records: [],
        }),
      } as never,
      {
        writeDailyReport: vi.fn().mockResolvedValue({
          filePath: "/tmp/mock-erp-daily.csv",
          fileName: "mock-erp-daily.csv",
        }),
      } as never,
      {
        sendErpReport,
      } as never,
    );

    await runner({
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
    });

    expect(sendErpReport).toHaveBeenCalledOnce();
  });
});
