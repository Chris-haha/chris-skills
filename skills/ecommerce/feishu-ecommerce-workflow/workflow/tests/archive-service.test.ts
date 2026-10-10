import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { ArchiveService } from "../src/services/archive-service";

describe("ArchiveService", () => {
  it("writes images into a task folder and creates a zip file", async () => {
    const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "workflow-archive-"));
    const service = new ArchiveService(tempDir);

    const result = await service.archive("task-1", [
      {
        fileName: "task-1-01.png",
        mimeType: "image/png",
        bytes: Buffer.from("test"),
      },
    ]);

    expect(result.taskDir).toContain("task-1");
    expect(result.zipPath.endsWith(".zip")).toBe(true);
    await expect(fs.stat(result.zipPath)).resolves.toBeDefined();
  });
});
