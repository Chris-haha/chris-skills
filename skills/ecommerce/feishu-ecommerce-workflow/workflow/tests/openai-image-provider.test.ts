import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImageTask } from "../src/types";

const generateMock = vi.fn();
const openAiCtorMock = vi.fn();

vi.mock("openai", () => ({
  default: vi.fn().mockImplementation((options: unknown) => {
    openAiCtorMock(options);
    return {
      images: {
        generate: generateMock,
      },
    };
  }),
}));

describe("OpenAiImageProvider", () => {
  const task: ImageTask = {
    recordId: "rec-1",
    taskSeq: 1,
    taskId: "task-1",
    productName: "MacBook Pro",
    ownerOpenId: "ou_123",
    ownerDisplayName: "张三",
    promptTemplate: "premium poster",
    imageCount: 1,
    retryCount: 0,
    status: "待处理",
  };

  beforeEach(() => {
    generateMock.mockReset();
    openAiCtorMock.mockReset();
  });

  it("normalizes a root base URL to /v1 and uses a configurable model", async () => {
    const { OpenAiImageProvider } = await import(
      "../src/providers/openai-image-provider"
    );
    generateMock.mockResolvedValue({
      data: [
        {
          b64_json: Buffer.from("png-bytes").toString("base64"),
        },
      ],
    });

    const provider = new OpenAiImageProvider(
      "sk-test",
      "https://gateway.example.com",
      "gpt-image-2",
    );

    await provider.generate(task);

    expect(openAiCtorMock).toHaveBeenCalledWith({
      apiKey: "sk-test",
      baseURL: "https://gateway.example.com/v1",
    });
    expect(generateMock).toHaveBeenCalledWith({
      model: "gpt-image-2",
      prompt: "MacBook Pro: premium poster",
      response_format: "b64_json",
      size: "1024x1024",
    });
  });

  it("omits response format for the default gpt-image-1 model", async () => {
    const { OpenAiImageProvider } = await import(
      "../src/providers/openai-image-provider"
    );
    generateMock.mockResolvedValue({
      data: [
        {
          b64_json: Buffer.from("png-bytes").toString("base64"),
        },
      ],
    });

    const provider = new OpenAiImageProvider("sk-test");

    await provider.generate(task);

    expect(generateMock).toHaveBeenCalledWith({
      model: "gpt-image-1",
      prompt: "MacBook Pro: premium poster",
      size: "1024x1024",
    });
  });

  it("downloads image bytes when the gateway returns a URL instead of base64", async () => {
    const { OpenAiImageProvider } = await import(
      "../src/providers/openai-image-provider"
    );
    generateMock.mockResolvedValue({
      data: [
        {
          url: "https://gateway.example.com/files/task-1.png",
        },
      ],
    });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue({
        ok: true,
        arrayBuffer: async () => Uint8Array.from([1, 2, 3]).buffer,
      } as Response);

    const provider = new OpenAiImageProvider(
      "sk-test",
      "https://gateway.example.com",
      "gpt-image-2",
    );

    const results = await provider.generate(task);

    expect(fetchMock).toHaveBeenCalledWith(
      "https://gateway.example.com/files/task-1.png",
    );
    expect(results).toHaveLength(1);
    expect(results[0].bytes.equals(Buffer.from([1, 2, 3]))).toBe(true);
    fetchMock.mockRestore();
  });
});
