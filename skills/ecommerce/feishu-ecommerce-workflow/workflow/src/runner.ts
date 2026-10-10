import { pathToFileURL } from "node:url";
import { FeishuAdapter } from "./adapters/feishu";
import { loadConfig } from "./config";
import type { ErpDataProvider } from "./providers/erp-data-provider";
import type { ImageProvider } from "./providers/image-provider";
import { MockErpDataProvider } from "./providers/mock-erp-data-provider";
import { MockImageProvider } from "./providers/mock-image-provider";
import { OpenAiImageProvider } from "./providers/openai-image-provider";
import { ArchiveService } from "./services/archive-service";
import { ReportService } from "./services/report-service";
import { TaskLoopRunner } from "./services/task-loop-runner";
import { TaskRunner } from "./services/task-runner";

type RunnerMode = "run-once" | "run-loop" | "rerun-task" | "erp-report";
type RunOptions = {
  taskId?: string;
  confirmRerunCompleted?: boolean;
  ownerOpenId?: string;
  ownerDisplayName?: string;
};
type RerunOptions = {
  confirmRerunCompleted: boolean;
};
type ErpReportOwner = {
  ownerOpenId: string;
  ownerDisplayName: string;
};

type RunnerDeps = {
  buildFeishuAdapter?: (config: ReturnType<typeof loadConfig>) => FeishuAdapter;
  buildTaskRunner?: (
    config: ReturnType<typeof loadConfig>,
    imageProvider: ImageProvider,
    feishuAdapter: FeishuAdapter,
  ) => TaskRunner;
  buildTaskLoopRunner?: (
    config: ReturnType<typeof loadConfig>,
    runBatch: () => Promise<void>,
  ) => Pick<TaskLoopRunner, "runForever">;
  buildErpDataProvider?: () => Pick<ErpDataProvider, "getDailyReport">;
  buildReportService?: (
    config: ReturnType<typeof loadConfig>,
  ) => Pick<ReportService, "writeDailyReport">;
};

export function createTaskRerunner(
  adapter: Pick<FeishuAdapter, "findTaskByTaskId" | "resetTaskForRerun">,
  options: RerunOptions,
  taskRunner: Pick<TaskRunner, "runOnce">,
) {
  return async function rerunTask(taskId: string): Promise<void> {
    const task = await adapter.findTaskByTaskId(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found.`);
    }

    if (task.status === "已完成" && !options.confirmRerunCompleted) {
      throw new Error(
        `Rerunning completed task ${taskId} requires confirmation.`,
      );
    }

    if (task.status === "已完成") {
      await adapter.resetTaskForRerun(task.recordId, task.ownerDisplayName);
    }

    await taskRunner.runOnce();
  };
}

export function createErpReportRunner(
  provider: Pick<ErpDataProvider, "getDailyReport">,
  reportService: Pick<ReportService, "writeDailyReport">,
  feishuAdapter: Pick<FeishuAdapter, "sendErpReport">,
) {
  return async function runErpReport(owner: ErpReportOwner): Promise<void> {
    const report = await provider.getDailyReport();
    const generatedAt = new Date().toISOString();
    const reportTitle = `${generatedAt.slice(0, 10)} 运营日报`;
    const artifact = await reportService.writeDailyReport({
      reportName: "mock-erp-daily",
      generatedAt,
      summary: report.summary,
      records: report.records,
    });

    await feishuAdapter.sendErpReport(
      owner.ownerOpenId,
      owner.ownerDisplayName,
      reportTitle,
      artifact.filePath,
      `总销售额 ${report.summary.totalSales}，订单数 ${report.summary.totalOrders}`,
    );
  };
}

export function createRunner(
  env: Record<string, string | undefined> = process.env,
  deps: RunnerDeps = {},
) {
  return async function run(
    mode: RunnerMode = "run-once",
    options: RunOptions = {},
  ): Promise<void> {
    const config = loadConfig(env);
    const imageProvider =
      config.imageProvider === "openai"
        ? new OpenAiImageProvider(
            config.openaiApiKey ?? "",
            config.openaiBaseUrl,
            config.openaiImageModel,
          )
        : new MockImageProvider();
    const feishuAdapter =
      deps.buildFeishuAdapter?.(config) ??
      new FeishuAdapter({
        appId: config.feishuAppId,
        appSecret: config.feishuAppSecret,
        appToken: config.feishuAppToken,
        tableId: config.feishuTableId,
        webhook: config.feishuBotWebhook,
      });
    const taskRunner =
      deps.buildTaskRunner?.(config, imageProvider, feishuAdapter) ??
      new TaskRunner(
        feishuAdapter,
        imageProvider,
        new ArchiveService(config.outputDir),
      );
    const erpDataProvider =
      deps.buildErpDataProvider?.() ?? new MockErpDataProvider();
    const reportService =
      deps.buildReportService?.(config) ?? new ReportService(config.outputDir);

    if (mode === "rerun-task") {
      if (!options.taskId) {
        throw new Error("rerun-task requires a task_id argument.");
      }

      const rerun = createTaskRerunner(
        feishuAdapter,
        {
          confirmRerunCompleted: options.confirmRerunCompleted === true,
        },
        taskRunner,
      );
      await rerun(options.taskId);
      return;
    }

    if (mode === "erp-report") {
      const ownerOpenId = options.ownerOpenId ?? env.ERP_REPORT_OWNER_OPEN_ID ?? "";
      const ownerDisplayName =
        options.ownerDisplayName ?? env.ERP_REPORT_OWNER_DISPLAY_NAME ?? "";
      if (!ownerOpenId) {
        throw new Error("ERP_REPORT_OWNER_OPEN_ID is required.");
      }

      const reportRunner = createErpReportRunner(
        erpDataProvider,
        reportService,
        feishuAdapter,
      );
      await reportRunner({ ownerOpenId, ownerDisplayName });
      return;
    }

    if (mode === "run-loop") {
      if (!config.autoRunEnabled) {
        throw new Error("AUTO_RUN_ENABLED is false; loop mode is disabled.");
      }

      const taskLoopRunner =
        deps.buildTaskLoopRunner?.(config, () => taskRunner.runOnce()) ??
        new TaskLoopRunner(
          () => taskRunner.runOnce(),
          config.autoRunIntervalMinutes,
        );

      await taskLoopRunner.runForever();
      return;
    }

    await taskRunner.runOnce();
  };
}

export function createTaskSeeder(
  env: Record<string, string | undefined> = process.env,
) {
  return async function seedTask(): Promise<void> {
    const config = loadConfig(env);
    const adapter = new FeishuAdapter({
      appId: config.feishuAppId,
      appSecret: config.feishuAppSecret,
      appToken: config.feishuAppToken,
      tableId: config.feishuTableId,
      webhook: config.feishuBotWebhook,
    });

    const result = await adapter.createTask({
      taskId: "iphone-pro-test",
      productName: "iPhone Pro",
      ownerOpenId: env.SEED_OWNER_OPEN_ID ?? "",
      ownerDisplayName: env.SEED_OWNER_DISPLAY_NAME ?? "",
      promptTemplate: "phone hero",
      imageCount: 1,
      retryCount: 0,
      taskStatus: "待处理",
      statusNote: "",
    });

    console.log(
      JSON.stringify(
        {
          taskId: "iphone-pro-test",
          recordId: result.recordId,
          taskSeq: result.taskSeq,
        },
        null,
        2,
      ),
    );
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const mode = process.argv[2];
  const taskId = process.argv[3];
  const confirmRerunCompleted = process.argv.includes(
    "--confirm-rerun-completed",
  );
  const run =
    mode === "seed-task"
      ? createTaskSeeder()
      : () =>
          createRunner()(
            mode === "run-loop"
              ? "run-loop"
              : mode === "rerun-task"
                ? "rerun-task"
                : mode === "erp-report"
                  ? "erp-report"
                : "run-once",
            {
              taskId,
              confirmRerunCompleted,
              ownerOpenId: process.env.ERP_REPORT_OWNER_OPEN_ID,
              ownerDisplayName: process.env.ERP_REPORT_OWNER_DISPLAY_NAME,
            },
          );
  run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
