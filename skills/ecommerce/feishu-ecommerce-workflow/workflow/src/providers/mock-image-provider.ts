import { Buffer } from "node:buffer";
import type { GeneratedImage, ImageTask } from "../types";
import type { ImageProvider } from "./image-provider";

const ONE_PIXEL_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9dZYcAAAAASUVORK5CYII=";

export class MockImageProvider implements ImageProvider {
  async generate(task: ImageTask): Promise<GeneratedImage[]> {
    return Array.from({ length: task.imageCount }, (_, index) => ({
      fileName: `${task.taskId}-${String(index + 1).padStart(2, "0")}.png`,
      mimeType: "image/png",
      bytes: Buffer.from(ONE_PIXEL_PNG_BASE64, "base64"),
    }));
  }
}
