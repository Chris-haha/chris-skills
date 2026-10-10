import type { FeishuAdapter } from "../adapters/feishu";
import type { ImageProvider } from "../providers/image-provider";
import type { ArchiveService } from "./archive-service";

export class TaskRunner {
  constructor(
    private readonly feishuAdapter: FeishuAdapter,
    private readonly imageProvider: ImageProvider,
    private readonly archiveService: ArchiveService,
  ) {}

  async runOnce(): Promise<void> {
    const tasks = await this.feishuAdapter.listPendingTasks();

    for (const task of tasks) {
      try {
        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "排队中",
          "",
          task.ownerDisplayName,
        );
        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "生成中",
          "",
          task.ownerDisplayName,
        );

        const images = await this.imageProvider.generate(task);

        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "打包中",
          "",
          task.ownerDisplayName,
        );
        const archive = await this.archiveService.archive(task.taskId, images);

        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "发送中",
          archive.zipPath,
          task.ownerDisplayName,
        );
        await this.feishuAdapter.sendTaskResult(
          task.ownerOpenId,
          task.ownerDisplayName,
          archive.zipPath,
          task.taskId,
        );

        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "已完成",
          archive.zipPath,
          task.ownerDisplayName,
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        await this.feishuAdapter.updateTaskStatus(
          task.recordId,
          "失败待重试",
          message,
          task.ownerDisplayName,
        );
      }
    }
  }
}
