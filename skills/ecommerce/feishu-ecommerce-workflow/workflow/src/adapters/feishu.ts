import { randomUUID } from "node:crypto";
import type { ImageTask, TaskStatus } from "../types";

type FeishuConfig = {
  appId: string;
  appSecret: string;
  appToken: string;
  tableId: string;
  webhook: string;
};

type FetchLike = typeof fetch;

type CreateTaskInput = {
  taskId: string;
  productName: string;
  ownerOpenId: string;
  ownerDisplayName: string;
  promptTemplate: string;
  imageCount: number;
  retryCount: number;
  taskStatus: TaskStatus;
  statusNote: string;
};

type CreateTaskResult = {
  recordId: string;
  taskSeq: number;
};

function readTextField(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }

  if (Array.isArray(value) && value[0] && typeof value[0] === "object" && "text" in value[0]) {
    return String((value[0] as { text: string }).text);
  }

  return "";
}

function readNumberField(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  const parsed = Number(readTextField(value));
  return Number.isFinite(parsed) ? parsed : 0;
}

export class FeishuAdapter {
  private tenantAccessToken: string | null = null;
  private readonly ownerNameCache = new Map<string, string>();

  constructor(
    private readonly config: FeishuConfig,
    private readonly fetcher: FetchLike = fetch,
  ) {}

  private async getTenantAccessToken(): Promise<string> {
    if (this.tenantAccessToken) {
      return this.tenantAccessToken;
    }

    const response = await this.fetcher(
      "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          app_id: this.config.appId,
          app_secret: this.config.appSecret,
        }),
      },
    );
    const payload = await response.json();
    const token = String(payload.tenant_access_token ?? "");
    if (!token) {
      throw new Error("Missing tenant_access_token from Feishu auth response.");
    }

    this.tenantAccessToken = token;
    return token;
  }

  private async requestJson(url: string, init: RequestInit): Promise<any> {
    const response = await this.fetcher(url, init);
    const payload = await response.json();
    if (!response.ok || (typeof payload.code === "number" && payload.code !== 0)) {
      throw new Error(
        String(payload.msg ?? payload.error?.message ?? "Feishu request failed"),
      );
    }

    return payload;
  }

  private async listAllRecords(): Promise<any[]> {
    const tenantAccessToken = await this.getTenantAccessToken();
    const items: any[] = [];
    let pageToken: string | undefined;

    for (;;) {
      const url = new URL(
        `https://open.feishu.cn/open-apis/bitable/v1/apps/${this.config.appToken}/tables/${this.config.tableId}/records`,
      );
      url.searchParams.set("automatic_fields", "true");
      url.searchParams.set("page_size", "500");
      if (pageToken) {
        url.searchParams.set("page_token", pageToken);
      }

      const payload = await this.requestJson(url.toString(), {
        method: "GET",
        headers: {
          Authorization: `Bearer ${tenantAccessToken}`,
        },
      });

      items.push(...(payload.data?.items ?? []));
      if (!payload.data?.has_more) {
        return items;
      }

      pageToken = payload.data?.page_token;
      if (!pageToken) {
        return items;
      }
    }
  }

  private async buildTaskItems(): Promise<ImageTask[]> {
    const records = await this.listAllRecords();

    const tasks = await Promise.all(
      records.map(async (item: any) => {
        const ownerOpenId = readTextField(item.fields.owner_open_id);
        const ownerDisplayName = await this.resolveOwnerDisplayName(
          ownerOpenId,
          readTextField(item.fields.owner_display_name),
        );

        return {
          recordId: item.record_id,
          taskSeq: readNumberField(item.fields.task_seq),
          taskId: readTextField(item.fields.task_id),
          productName: readTextField(item.fields.product_name),
          ownerOpenId,
          ownerDisplayName,
          promptTemplate: readTextField(item.fields.prompt_template),
          imageCount: Number(item.fields.image_count ?? 1),
          retryCount: Number(item.fields.retry_count ?? 0),
          status: item.fields.task_status as TaskStatus,
        };
      }),
    );

    return tasks.sort((left, right) => {
      if (left.taskSeq !== right.taskSeq) {
        return left.taskSeq - right.taskSeq;
      }

      return left.recordId.localeCompare(right.recordId);
    });
  }

  private async getNextTaskSeq(): Promise<number> {
    const records = await this.buildTaskItems();
    const maxSeq = records.reduce((max, item: ImageTask) => {
      return Math.max(max, item.taskSeq);
    }, 0);
    return maxSeq + 1;
  }

  private async getUserDisplayName(ownerOpenId: string): Promise<string> {
    if (!ownerOpenId) {
      return "";
    }

    const cached = this.ownerNameCache.get(ownerOpenId);
    if (cached) {
      return cached;
    }

    const tenantAccessToken = await this.getTenantAccessToken();
    try {
      const payload = await this.requestJson(
        `https://open.feishu.cn/open-apis/contact/v3/users/${ownerOpenId}?user_id_type=open_id`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${tenantAccessToken}`,
          },
        },
      );
      const displayName = readTextField(payload.data?.user?.name);
      const resolvedName = displayName || ownerOpenId;
      this.ownerNameCache.set(ownerOpenId, resolvedName);
      return resolvedName;
    } catch {
      this.ownerNameCache.set(ownerOpenId, ownerOpenId);
      return ownerOpenId;
    }
  }

  async resolveOwnerDisplayName(
    ownerOpenId: string,
    ownerDisplayName: string,
  ): Promise<string> {
    if (ownerDisplayName) {
      this.ownerNameCache.set(ownerOpenId, ownerDisplayName);
      return ownerDisplayName;
    }

    return this.getUserDisplayName(ownerOpenId);
  }

  async listPendingTasks(): Promise<ImageTask[]> {
    const tasks = await this.buildTaskItems();

    return tasks
      .filter(
        (task: ImageTask) =>
          task.status === "待处理" || task.status === "失败待重试",
      );
  }

  async findTaskByTaskId(taskId: string): Promise<ImageTask | null> {
    const tasks = await this.buildTaskItems();
    return tasks.find((task) => task.taskId === taskId) ?? null;
  }

  async resetTaskForRerun(
    recordId: string,
    ownerDisplayName: string,
  ): Promise<void> {
    const tenantAccessToken = await this.getTenantAccessToken();
    await this.requestJson(
      `https://open.feishu.cn/open-apis/bitable/v1/apps/${this.config.appToken}/tables/${this.config.tableId}/records/${recordId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tenantAccessToken}`,
        },
        body: JSON.stringify({
          fields: {
            task_status: "待处理",
            status_note: "",
            owner_display_name: ownerDisplayName,
          },
        }),
      },
    );
  }

  async createTask(input: CreateTaskInput): Promise<CreateTaskResult> {
    const tenantAccessToken = await this.getTenantAccessToken();
    const taskSeq = await this.getNextTaskSeq();
    const payload = await this.requestJson(
      `https://open.feishu.cn/open-apis/bitable/v1/apps/${this.config.appToken}/tables/${this.config.tableId}/records`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          Authorization: `Bearer ${tenantAccessToken}`,
        },
        body: JSON.stringify({
          client_token: randomUUID(),
          fields: {
            task_seq: taskSeq,
            task_id: input.taskId,
            product_name: input.productName,
            owner_open_id: input.ownerOpenId,
            owner_display_name: input.ownerDisplayName,
            prompt_template: input.promptTemplate,
            image_count: input.imageCount,
            retry_count: input.retryCount,
            task_status: input.taskStatus,
            status_note: input.statusNote,
          },
        }),
      },
    );

    return {
      recordId: String(payload.data?.record?.record_id ?? payload.data?.record_id ?? ""),
      taskSeq,
    };
  }

  async updateTaskStatus(
    recordId: string,
    status: TaskStatus,
    note: string,
    ownerDisplayName: string,
  ): Promise<void> {
    const tenantAccessToken = await this.getTenantAccessToken();
    await this.requestJson(
      `https://open.feishu.cn/open-apis/bitable/v1/apps/${this.config.appToken}/tables/${this.config.tableId}/records/${recordId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${tenantAccessToken}`,
        },
        body: JSON.stringify({
          fields: {
            task_status: status,
            status_note: note,
            owner_display_name: ownerDisplayName,
          },
        }),
      },
    );
  }

  async sendTaskResult(
    ownerOpenId: string,
    ownerDisplayName: string,
    zipPath: string,
    taskId: string,
  ): Promise<void> {
    await this.requestJson(this.config.webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        msg_type: "text",
        content: {
          text: `任务 ${taskId} 已完成，产物路径：${zipPath}，负责人：<at user_id="${ownerOpenId}">${ownerDisplayName || ownerOpenId}</at>`,
        },
      }),
    });
  }

  async sendErpReport(
    ownerOpenId: string,
    ownerDisplayName: string,
    reportTitle: string,
    filePath: string,
    summary: string,
  ): Promise<void> {
    await this.requestJson(this.config.webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        msg_type: "text",
        content: {
          text:
            `运营报表 ${reportTitle} 已生成，摘要：${summary}，文件路径：${filePath}，负责人：` +
            `<at user_id="${ownerOpenId}">${ownerDisplayName || ownerOpenId}</at>`,
        },
      }),
    });
  }
}
