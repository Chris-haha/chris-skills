import { describe, expect, it, vi } from "vitest";
import { FeishuAdapter } from "../src/adapters/feishu";

describe("FeishuAdapter", () => {
  it("requests a tenant access token and uses it for bitable reads", async () => {
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
                  task_seq: [{ text: "6" }],
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
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            user: {
              name: "张三",
            },
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

    const tasks = await adapter.listPendingTasks();

    expect(tasks).toHaveLength(1);
    expect(tasks[0].ownerDisplayName).toBe("张三");
    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining(
        "https://open.feishu.cn/open-apis/bitable/v1/apps/token/tables/table-id/records",
      ),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer tenant-token",
        }),
      }),
    );
  });

  it("maps flat string values from real bitable records", async () => {
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
                  task_seq: "6",
                  task_id: "task-1",
                  product_name: "Demo Product",
                  owner_open_id: "ou_123",
                  owner_display_name: "张三",
                  prompt_template: "hero",
                  image_count: "2",
                  retry_count: "0",
                  task_status: "待处理",
                },
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            user: {
              name: "张三",
            },
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

    const tasks = await adapter.listPendingTasks();

    expect(tasks).toHaveLength(1);
    expect(tasks[0]).toMatchObject({
      taskId: "task-1",
      productName: "Demo Product",
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
      promptTemplate: "hero",
      imageCount: 2,
      retryCount: 0,
      status: "待处理",
    });
  });

  it("prefers the display name already stored in the table", async () => {
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
                  task_seq: 5,
                  task_id: "task-1",
                  product_name: "Demo Product",
                  owner_open_id: "ou_123",
                  owner_display_name: "李四",
                  prompt_template: "hero",
                  image_count: "2",
                  retry_count: "0",
                  task_status: "待处理",
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

    const tasks = await adapter.listPendingTasks();

    expect(tasks).toHaveLength(1);
    expect(tasks[0]?.ownerDisplayName).toBe("李四");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("sorts pending tasks by task_seq ascending", async () => {
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
                record_id: "rec-2",
                fields: {
                  task_seq: 2,
                  task_id: "task-2",
                  product_name: "Second",
                  owner_open_id: "ou_123",
                  owner_display_name: "张三",
                  prompt_template: "hero",
                  image_count: 1,
                  retry_count: 0,
                  task_status: "待处理",
                },
              },
              {
                record_id: "rec-1",
                fields: {
                  task_seq: 1,
                  task_id: "task-1",
                  product_name: "First",
                  owner_open_id: "ou_123",
                  owner_display_name: "张三",
                  prompt_template: "hero",
                  image_count: 1,
                  retry_count: 0,
                  task_status: "待处理",
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

    const tasks = await adapter.listPendingTasks();

    expect(tasks.map((task) => task.taskSeq)).toEqual([1, 2]);
  });

  it("mentions the owner in the webhook message", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ok: true,
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

    await adapter.sendTaskResult(
      "ou_123",
      "张三",
      "/tmp/task-1.zip",
      "task-1",
    );

    expect(fetcher).toHaveBeenCalledTimes(1);
    const call = fetcher.mock.calls[0];
    expect(call?.[0]).toBe("https://example.com/webhook");
    const body = JSON.parse(
      String((call?.[1] as RequestInit | undefined)?.body),
    ) as { content?: { text?: string } };
    expect(body.content?.text).toContain('<at user_id="ou_123">张三</at>');
  });

  it("sends an ERP report summary message with owner mention", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ok: true,
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

    await adapter.sendErpReport(
      "ou_123",
      "张三",
      "2026-07-26 运营日报",
      "/tmp/mock-erp-daily.csv",
      "总销售额 152340.5，订单数 328",
    );

    const call = fetcher.mock.calls[0];
    const body = JSON.parse(
      String((call?.[1] as RequestInit | undefined)?.body),
    ) as { content?: { text?: string } };

    expect(body.content?.text).toContain("2026-07-26 运营日报");
    expect(body.content?.text).toContain("总销售额 152340.5，订单数 328");
    expect(body.content?.text).toContain('<at user_id="ou_123">张三</at>');
  });

  it("writes the owner display name back when updating task status", async () => {
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
          ok: true,
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

    await adapter.updateTaskStatus("rec-1", "生成中", "", "张三");

    const call = fetcher.mock.calls[1];
    const body = JSON.parse(
      String((call?.[1] as RequestInit | undefined)?.body),
    ) as { fields?: Record<string, unknown> };

    expect(body.fields).toMatchObject({
      task_status: "生成中",
      status_note: "",
      owner_display_name: "张三",
    });
  });

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
        json: async () => ({
          ok: true,
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

  it("creates the next task sequence from existing records", async () => {
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
                record_id: "rec-5",
                fields: {
                  task_seq: 5,
                },
              },
              {
                record_id: "rec-2",
                fields: {
                  task_seq: 2,
                },
              },
            ],
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          data: {
            record: {
              record_id: "rec-new",
            },
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

    const result = await adapter.createTask({
      taskId: "iphone-pro-test",
      productName: "iPhone Pro",
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
      promptTemplate: "phone hero",
      imageCount: 1,
      retryCount: 0,
      taskStatus: "待处理",
      statusNote: "",
    });

    expect(result.taskSeq).toBe(6);
    expect(result.recordId).toBe("rec-new");
    const body = JSON.parse(
      String((fetcher.mock.calls[2]?.[1] as RequestInit | undefined)?.body),
    ) as { fields?: Record<string, unknown>; client_token?: string };

    expect(body.client_token).toBeTruthy();
    expect(body.fields).toMatchObject({
      task_seq: 6,
      task_id: "iphone-pro-test",
      product_name: "iPhone Pro",
      owner_open_id: "ou_123",
      owner_display_name: "张三",
      prompt_template: "phone hero",
      image_count: 1,
      retry_count: 0,
      task_status: "待处理",
      status_note: "",
    });
  });

  it("throws the Feishu error message when bitable read is unauthorized", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tenant_access_token: "tenant-token",
        }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          msg: "Missing access token for authorization.",
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

    await expect(adapter.listPendingTasks()).rejects.toThrow(
      "Missing access token for authorization.",
    );
  });
});
