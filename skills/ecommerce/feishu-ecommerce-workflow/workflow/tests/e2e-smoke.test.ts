import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import { FeishuAdapter } from "../src/adapters/feishu";
import { createRunner } from "../src/runner";
import { MockImageProvider } from "../src/providers/mock-image-provider";
import { ArchiveService } from "../src/services/archive-service";
import { TaskRunner } from "../src/services/task-runner";

describe("end-to-end smoke flow", () => {
  it("processes one task from Feishu read to zip notification", async () => {
    const outputDir = await fs.mkdtemp(path.join(os.tmpdir(), "workflow-e2e-"));
    const calls: Array<{ url: string; method: string; body?: unknown }> = [];

    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.push({ url, method, body });

      if (url.includes("/auth/v3/tenant_access_token/internal")) {
        return {
          ok: true,
          json: async () => ({
            tenant_access_token: "tenant-token",
          }),
        } as Response;
      }

      if (method === "GET") {
        return {
          ok: true,
          json: async () => ({
            data: {
              items: [
                {
                  record_id: "rec-1",
                  fields: {
                    task_seq: [{ text: "1" }],
                    task_id: [{ text: "task-1" }],
                    product_name: [{ text: "Demo Product" }],
                    owner_open_id: [{ text: "ou_123" }],
                    owner_display_name: [{ text: "张三" }],
                    prompt_template: [{ text: "hero" }],
                    image_count: 2,
                    retry_count: 0,
                    task_status: "待处理",
                  },
                },
              ],
            },
          }),
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({ ok: true }),
      } as Response;
    });

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "mock",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: outputDir,
        RETENTION_DAYS: "7",
      },
      {
        buildTaskRunner: () =>
          new TaskRunner(
            new FeishuAdapter(
              {
                appId: "app-id",
                appSecret: "app-secret",
                appToken: "app-token",
                tableId: "table-id",
                webhook: "https://example.com/hook",
              },
              fetcher as unknown as typeof fetch,
            ),
            new MockImageProvider(),
            new ArchiveService(outputDir),
          ),
      },
    );

    await runner();

    expect(
      calls.filter((call) =>
        call.url.includes("/auth/v3/tenant_access_token/internal"),
      ),
    ).toHaveLength(1);
    expect(
      calls.filter(
        (call) =>
          call.method === "GET" &&
          call.url.includes("/bitable/v1/apps/"),
      ),
    ).toHaveLength(1);
    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(5);
    expect(
      calls.filter(
        (call) =>
          call.method === "POST" &&
          !call.url.includes("/auth/v3/tenant_access_token/internal") &&
          call.url === "https://example.com/hook",
      ),
    ).toHaveLength(1);
    await expect(
      fs.stat(path.join(outputDir, "task-1.zip")),
    ).resolves.toBeDefined();
  });

  it("routes rerun-task mode through reset and batch execution", async () => {
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

    const runner = createRunner(
      {
        IMAGE_PROVIDER: "mock",
        FEISHU_APP_ID: "app-id",
        FEISHU_APP_SECRET: "app-secret",
        FEISHU_APP_TOKEN: "app-token",
        FEISHU_TABLE_ID: "table-id",
        FEISHU_BOT_WEBHOOK: "https://example.com/hook",
        OUTPUT_DIR: "/tmp",
        RETENTION_DAYS: "7",
      },
      {
        buildFeishuAdapter: () => adapter as never,
        buildTaskRunner: () => ({ runOnce }) as never,
      } as never,
    );

    await runner("rerun-task", {
      taskId: "iphone-pro-test",
      confirmRerunCompleted: true,
    });

    expect(adapter.resetTaskForRerun).toHaveBeenCalledWith("rec-1", "张三");
    expect(runOnce).toHaveBeenCalledOnce();
  });
});
