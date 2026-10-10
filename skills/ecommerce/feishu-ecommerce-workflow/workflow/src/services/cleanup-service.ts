import fs from "node:fs/promises";
import path from "node:path";

export class CleanupService {
  constructor(
    private readonly outputDir: string,
    private readonly retentionDays: number,
  ) {}

  async deleteExpired(now = new Date()): Promise<string[]> {
    const entries = await fs
      .readdir(this.outputDir, { withFileTypes: true })
      .catch(() => []);
    const deleted: string[] = [];
    const cutoff = now.getTime() - this.retentionDays * 24 * 60 * 60 * 1000;

    for (const entry of entries) {
      const fullPath = path.join(this.outputDir, entry.name);
      const stat = await fs.stat(fullPath);
      if (stat.mtimeMs >= cutoff) {
        continue;
      }

      await fs.rm(fullPath, { recursive: true, force: true });
      deleted.push(fullPath);
    }

    return deleted;
  }
}
