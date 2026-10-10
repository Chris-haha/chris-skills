import fs from "node:fs/promises";
import path from "node:path";
import AdmZip from "adm-zip";
import type { GeneratedImage } from "../types";

export type ArchiveResult = {
  taskDir: string;
  zipPath: string;
};

export class ArchiveService {
  constructor(private readonly outputDir: string) {}

  async archive(taskId: string, images: GeneratedImage[]): Promise<ArchiveResult> {
    const taskDir = path.join(this.outputDir, taskId);
    await fs.mkdir(taskDir, { recursive: true });

    for (const image of images) {
      await fs.writeFile(path.join(taskDir, image.fileName), image.bytes);
    }

    const zip = new AdmZip();
    for (const image of images) {
      zip.addLocalFile(path.join(taskDir, image.fileName));
    }

    const zipPath = path.join(this.outputDir, `${taskId}.zip`);
    zip.writeZip(zipPath);

    return { taskDir, zipPath };
  }
}
