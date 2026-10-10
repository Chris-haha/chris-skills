import { describe, expect, it } from "vitest";
import { loadConfig } from "../src/config";

describe("loadConfig", () => {
  it("loads required env and defaults image provider to mock", () => {
    const config = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
    });

    expect(config.imageProvider).toBe("mock");
    expect(config.retentionDays).toBe(7);
    expect(config.outputDir).toContain("data");
  });

  it("loads an optional OpenAI-compatible base URL", () => {
    const config = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
      IMAGE_PROVIDER: "openai",
      OPENAI_API_KEY: "sk-test",
      OPENAI_BASE_URL: "https://gateway.example.com/v1",
    });

    expect(config.openaiBaseUrl).toBe("https://gateway.example.com/v1");
  });

  it("defaults the image model and allows overriding it", () => {
    const defaultConfig = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
      IMAGE_PROVIDER: "openai",
      OPENAI_API_KEY: "sk-test",
    });
    const customConfig = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
      IMAGE_PROVIDER: "openai",
      OPENAI_API_KEY: "sk-test",
      OPENAI_IMAGE_MODEL: "gpt-image-2",
    });

    expect(defaultConfig.openaiImageModel).toBe("gpt-image-1");
    expect(customConfig.openaiImageModel).toBe("gpt-image-2");
  });

  it("loads auto-run config with safe defaults", () => {
    const config = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
    });

    expect(config.autoRunEnabled).toBe(false);
    expect(config.autoRunIntervalMinutes).toBe(10);
  });

  it("loads explicit auto-run config overrides", () => {
    const config = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
      AUTO_RUN_ENABLED: "true",
      AUTO_RUN_INTERVAL_MINUTES: "3",
    });

    expect(config.autoRunEnabled).toBe(true);
    expect(config.autoRunIntervalMinutes).toBe(3);
  });

  it('parses AUTO_RUN_ENABLED="false" as boolean false', () => {
    const config = loadConfig({
      FEISHU_APP_ID: "app-id",
      FEISHU_APP_SECRET: "app-secret",
      FEISHU_APP_TOKEN: "app-token",
      FEISHU_TABLE_ID: "table-id",
      FEISHU_BOT_WEBHOOK: "https://example.com/hook",
      OUTPUT_DIR: "./data",
      RETENTION_DAYS: "7",
      AUTO_RUN_ENABLED: "false",
    });

    expect(config.autoRunEnabled).toBe(false);
  });
});
