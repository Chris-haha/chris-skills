import OpenAI from "openai";
import type { GeneratedImage, ImageTask } from "../types";
import type { ImageProvider } from "./image-provider";

type ImageGenerateParams = Parameters<OpenAI["images"]["generate"]>[0];
type ImageGenerateResult = {
  data?: Array<{
    b64_json?: string | null;
    url?: string | null;
  }>;
};

function normalizeBaseURL(baseURL?: string): string | undefined {
  if (!baseURL) {
    return undefined;
  }

  const parsed = new URL(baseURL);
  if (parsed.pathname === "/" || parsed.pathname === "") {
    parsed.pathname = "/v1";
  }

  return parsed.toString().replace(/\/$/, "");
}

async function downloadImage(url: string): Promise<Buffer> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download generated image: ${response.status}`);
  }

  return Buffer.from(await response.arrayBuffer());
}

export class OpenAiImageProvider implements ImageProvider {
  constructor(
    private readonly apiKey: string,
    readonly baseURL?: string,
    readonly model = "gpt-image-1",
  ) {}

  async generate(task: ImageTask): Promise<GeneratedImage[]> {
    const client = new OpenAI({
      apiKey: this.apiKey,
      baseURL: normalizeBaseURL(this.baseURL),
    });
    const params: ImageGenerateParams = {
      model: this.model,
      prompt: `${task.productName}: ${task.promptTemplate}`,
      size: "1024x1024",
    };
    if (this.model !== "gpt-image-1") {
      params.response_format = "b64_json";
    }
    const result = (await client.images.generate(params)) as ImageGenerateResult;

    return Promise.all(
      (result.data ?? []).map(async (item, index) => ({
        fileName: `${task.taskId}-${String(index + 1).padStart(2, "0")}.png`,
        mimeType: "image/png" as const,
        bytes: item.b64_json
          ? Buffer.from(item.b64_json, "base64")
          : item.url
            ? await downloadImage(item.url)
            : Buffer.from(""),
      })),
    );
  }
}
