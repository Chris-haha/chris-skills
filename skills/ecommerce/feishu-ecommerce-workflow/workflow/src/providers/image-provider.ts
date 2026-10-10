import type { GeneratedImage, ImageTask } from "../types";

export interface ImageProvider {
  generate(task: ImageTask): Promise<GeneratedImage[]>;
}
