import { describe, expect, it, vi } from "vitest";
import { TaskRunner } from "../src/services/task-runner";

describe("TaskRunner", () => {
  it("advances one pending task from generation through completion", async () => {
    const adapter = {
      listPendingTasks: vi.fn().mockResolvedValue([
        {
          recordId: "rec-1",
          taskSeq: 1,
          taskId: "task-1",
          productName: "Demo Product",
          ownerOpenId: "ou_123",
          ownerDisplayName: "张三",
          promptTemplate: "hero",
          imageCount: 1,
          retryCount: 0,
          status: "待处理",
        },
      ]),
      updateTaskStatus: vi.fn().mockResolvedValue(undefined),
      sendTaskResult: vi.fn().mockResolvedValue(undefined),
    };

    const provider = {
      generate: vi.fn().mockResolvedValue([
        {
          fileName: "task-1-01.png",
          mimeType: "image/png",
          bytes: Buffer.from("test"),
        },
      ]),
    };

    const archiveService = {
      archive: vi.fn().mockResolvedValue({
        taskDir: "/tmp/task-1",
        zipPath: "/tmp/task-1.zip",
      }),
    };

    const runner = new TaskRunner(
      adapter as any,
      provider as any,
      archiveService as any,
    );

    await runner.runOnce();

    expect(adapter.updateTaskStatus).toHaveBeenNthCalledWith(
      1,
      "rec-1",
      "排队中",
      "",
      "张三",
    );
    expect(adapter.updateTaskStatus).toHaveBeenNthCalledWith(
      2,
      "rec-1",
      "生成中",
      "",
      "张三",
    );
    expect(adapter.updateTaskStatus).toHaveBeenLastCalledWith(
      "rec-1",
      "已完成",
      expect.stringContaining("/tmp/task-1.zip"),
      "张三",
    );
    expect(adapter.sendTaskResult).toHaveBeenCalledWith(
      "ou_123",
      "张三",
      "/tmp/task-1.zip",
      "task-1",
    );
  });

  it("marks a task as retryable when image generation fails", async () => {
    const adapter = {
      listPendingTasks: vi.fn().mockResolvedValue([
        {
          recordId: "rec-1",
          taskSeq: 1,
          taskId: "task-1",
          productName: "Demo Product",
          ownerOpenId: "ou_123",
          ownerDisplayName: "张三",
          promptTemplate: "hero",
          imageCount: 1,
          retryCount: 0,
          status: "待处理",
        },
      ]),
      updateTaskStatus: vi.fn().mockResolvedValue(undefined),
      sendTaskResult: vi.fn().mockResolvedValue(undefined),
    };

    const provider = {
      generate: vi.fn().mockRejectedValue(new Error("boom")),
    };

    const archiveService = {
      archive: vi.fn(),
    };

    const runner = new TaskRunner(
      adapter as any,
      provider as any,
      archiveService as any,
    );

    await runner.runOnce();

    expect(adapter.updateTaskStatus).toHaveBeenNthCalledWith(
      1,
      "rec-1",
      "排队中",
      "",
      "张三",
    );
    expect(adapter.updateTaskStatus).toHaveBeenNthCalledWith(
      2,
      "rec-1",
      "生成中",
      "",
      "张三",
    );
    expect(adapter.updateTaskStatus).toHaveBeenLastCalledWith(
      "rec-1",
      "失败待重试",
      "boom",
      "张三",
    );
    expect(adapter.sendTaskResult).not.toHaveBeenCalled();
    expect(archiveService.archive).not.toHaveBeenCalled();
  });
});
