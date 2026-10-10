import path from "node:path";
import { z } from "zod";

const schema = z.object({
  FEISHU_APP_ID: z.string().min(1),
  FEISHU_APP_SECRET: z.string().min(1),
  FEISHU_APP_TOKEN: z.string().min(1),
  FEISHU_TABLE_ID: z.string().min(1),
  FEISHU_BOT_WEBHOOK: z.string().url(),
  OUTPUT_DIR: z.string().min(1),
  RETENTION_DAYS: z.coerce.number().int().positive(),
  AUTO_RUN_ENABLED: z
    .enum(["true", "false"])
    .optional()
    .transform((value) => value === "true"),
  AUTO_RUN_INTERVAL_MINUTES: z.coerce.number().int().positive().default(10),
  IMAGE_PROVIDER: z.enum(["mock", "openai"]).default("mock"),
  OPENAI_API_KEY: z.string().optional(),
  OPENAI_BASE_URL: z.string().url().optional(),
  OPENAI_IMAGE_MODEL: z.string().min(1).default("gpt-image-1"),
});

export type AppConfig = {
  feishuAppId: string;
  feishuAppSecret: string;
  feishuAppToken: string;
  feishuTableId: string;
  feishuBotWebhook: string;
  outputDir: string;
  retentionDays: number;
  autoRunEnabled: boolean;
  autoRunIntervalMinutes: number;
  imageProvider: "mock" | "openai";
  openaiApiKey?: string;
  openaiBaseUrl?: string;
  openaiImageModel: string;
};

export function loadConfig(
  env: Record<string, string | undefined> = process.env,
): AppConfig {
  const parsed = schema.parse({
    FEISHU_APP_ID: env.FEISHU_APP_ID,
    FEISHU_APP_SECRET: env.FEISHU_APP_SECRET,
    FEISHU_APP_TOKEN: env.FEISHU_APP_TOKEN,
    FEISHU_TABLE_ID: env.FEISHU_TABLE_ID,
    FEISHU_BOT_WEBHOOK: env.FEISHU_BOT_WEBHOOK,
    OUTPUT_DIR: env.OUTPUT_DIR,
    RETENTION_DAYS: env.RETENTION_DAYS,
    AUTO_RUN_ENABLED: env.AUTO_RUN_ENABLED,
    AUTO_RUN_INTERVAL_MINUTES: env.AUTO_RUN_INTERVAL_MINUTES,
    IMAGE_PROVIDER: env.IMAGE_PROVIDER,
    OPENAI_API_KEY: env.OPENAI_API_KEY,
    OPENAI_BASE_URL: env.OPENAI_BASE_URL,
    OPENAI_IMAGE_MODEL: env.OPENAI_IMAGE_MODEL,
  });

  return {
    feishuAppId: parsed.FEISHU_APP_ID,
    feishuAppSecret: parsed.FEISHU_APP_SECRET,
    feishuAppToken: parsed.FEISHU_APP_TOKEN,
    feishuTableId: parsed.FEISHU_TABLE_ID,
    feishuBotWebhook: parsed.FEISHU_BOT_WEBHOOK,
    outputDir: path.resolve(parsed.OUTPUT_DIR),
    retentionDays: parsed.RETENTION_DAYS,
    autoRunEnabled: parsed.AUTO_RUN_ENABLED,
    autoRunIntervalMinutes: parsed.AUTO_RUN_INTERVAL_MINUTES,
    imageProvider: parsed.IMAGE_PROVIDER,
    openaiApiKey: parsed.OPENAI_API_KEY,
    openaiBaseUrl: parsed.OPENAI_BASE_URL,
    openaiImageModel: parsed.OPENAI_IMAGE_MODEL,
  };
}
