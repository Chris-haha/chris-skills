import { describe, expect, it } from "vitest";
import { MockImageProvider } from "../src/providers/mock-image-provider";
import type { ImageTask } from "../src/types";

describe("MockImageProvider", () => {
  it("returns the requested number of deterministic png files", async () => {
    const provider = new MockImageProvider();
    const task: ImageTask = {
      recordId: "rec-1",
      taskSeq: 1,
      taskId: "task-1",
      productName: "Demo Product",
      ownerOpenId: "ou_123",
      ownerDisplayName: "张三",
      promptTemplate: "hero image",
      imageCount: 2,
      retryCount: 0,
      status: "待处理",
    };

    const results = await provider.generate(task);

    expect(results).toHaveLength(2);
    expect(results[0].fileName).toBe("task-1-01.png");
    expect(results[0].mimeType).toBe("image/png");
    expect(results[0].bytes.length).toBeGreaterThan(0);
  });
});
