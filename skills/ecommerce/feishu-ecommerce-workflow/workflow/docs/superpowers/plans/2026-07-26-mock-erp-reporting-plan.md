# Mock ERP 报表发送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不接入真实 ERP 的前提下，用稳定的假数据生成运营报表，并通过飞书把报表摘要与产物路径发送给指定负责人。

**Architecture:** 新增独立的 ERP 数据提供者与报表服务，避免把运营报表逻辑塞进现有生图执行器。`runner` 只负责模式分发，`MockErpDataProvider` 负责产出稳定数据，`ReportService` 负责写出 CSV，Feishu 适配层负责发送运营报表通知。

**Tech Stack:** TypeScript、Vitest、Node `fs/promises`、现有 Feishu webhook 发送能力、CSV 文本输出

---

## 文件结构与职责

- 新建 `src/providers/erp-data-provider.ts`
  定义 ERP 数据提供接口和报表数据类型。
- 新建 `src/providers/mock-erp-data-provider.ts`
  返回稳定、可预测的假运营数据。
- 新建 `src/services/report-service.ts`
  负责把 ERP 数据写成 CSV 文件。
- 修改 `src/adapters/feishu.ts`
  增加 ERP 报表通知发送方法。
- 修改 `src/runner.ts`
  增加 `erp-report` 模式。
- 新建 `tests/mock-erp-data-provider.test.ts`
  覆盖 Mock 数据稳定输出。
- 新建 `tests/report-service.test.ts`
  覆盖 CSV 内容与文件写出。
- 修改 `tests/feishu-adapter.test.ts`
  覆盖 ERP 报表消息格式。
- 修改 `tests/runner.test.ts`
  覆盖 `erp-report` 模式分发。
- 修改 `README.md`
  增加 Mock ERP 报表运行方式。

### Task 1: 定义 ERP 数据接口并写 Mock Provider 测试

**Files:**
- Create: `src/providers/erp-data-provider.ts`
- Create: `tests/mock-erp-data-provider.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import { describe, expect, it } from "vitest";
import { MockErpDataProvider } from "../src/providers/mock-erp-data-provider";

describe("MockErpDataProvider", () => {
  it("returns deterministic mock ERP records", async () => {
    const provider = new MockErpDataProvider();

    const report = await provider.getDailyReport();

    expect(report.summary.totalSales).toBe(152340.5);
    expect(report.summary.totalOrders).toBe(328);
    expect(report.records).toHaveLength(3);
    expect(report.records[0]).toMatchObject({
      shopName: "Shop Alpha",
      topSku: "SKU-MACBOOK-PRO-14",
    });
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/mock-erp-data-provider.test.ts`
Expected: FAIL，因为 ERP Provider 还不存在。

- [ ] **Step 3: 写最小接口定义**

```ts
export type ErpReportSummary = {
  totalSales: number;
  totalOrders: number;
  totalAdSpend: number;
  averageGrossMargin: number;
};

export type ErpReportRecord = {
  shopName: string;
  date: string;
  salesAmount: number;
  orderCount: number;
  adSpend: number;
  grossMargin: number;
  topSku: string;
};

export type ErpDailyReport = {
  summary: ErpReportSummary;
  records: ErpReportRecord[];
};

export interface ErpDataProvider {
  getDailyReport(): Promise<ErpDailyReport>;
}
```

- [ ] **Step 4: 写最小 Mock Provider**

```ts
import type { ErpDailyReport, ErpDataProvider } from "./erp-data-provider";

export class MockErpDataProvider implements ErpDataProvider {
  async getDailyReport(): Promise<ErpDailyReport> {
    return {
      summary: {
        totalSales: 152340.5,
        totalOrders: 328,
        totalAdSpend: 28120.3,
        averageGrossMargin: 0.34,
      },
      records: [
        {
          shopName: "Shop Alpha",
          date: "2026-07-26",
          salesAmount: 54320.2,
          orderCount: 108,
          adSpend: 9200.1,
          grossMargin: 0.36,
          topSku: "SKU-MACBOOK-PRO-14",
        },
        {
          shopName: "Shop Beta",
          date: "2026-07-26",
          salesAmount: 48210.1,
          orderCount: 96,
          adSpend: 8710.2,
          grossMargin: 0.31,
          topSku: "SKU-IPHONE-PRO",
        },
        {
          shopName: "Shop Gamma",
          date: "2026-07-26",
          salesAmount: 49810.2,
          orderCount: 124,
          adSpend: 10210,
          grossMargin: 0.35,
          topSku: "SKU-AIRPODS-PRO",
        },
      ],
    };
  }
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm test -- tests/mock-erp-data-provider.test.ts`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add tests/mock-erp-data-provider.test.ts src/providers/erp-data-provider.ts src/providers/mock-erp-data-provider.ts
git commit -m "feat: add mock erp data provider"
```

### Task 2: 增加 CSV 报表生成服务

**Files:**
- Create: `src/services/report-service.ts`
- Create: `tests/report-service.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { ReportService } from "../src/services/report-service";

describe("ReportService", () => {
  it("writes a CSV ERP report with summary and detail rows", async () => {
    const outputDir = await fs.mkdtemp(path.join(os.tmpdir(), "erp-report-"));
    const service = new ReportService(outputDir);

    const result = await service.writeDailyReport({
      reportName: "mock-erp-daily",
      generatedAt: "2026-07-26T10:00:00.000Z",
      summary: {
        totalSales: 152340.5,
        totalOrders: 328,
        totalAdSpend: 28120.3,
        averageGrossMargin: 0.34,
      },
      records: [
        {
          shopName: "Shop Alpha",
          date: "2026-07-26",
          salesAmount: 54320.2,
          orderCount: 108,
          adSpend: 9200.1,
          grossMargin: 0.36,
          topSku: "SKU-MACBOOK-PRO-14",
        },
      ],
    });

    const csv = await fs.readFile(result.filePath, "utf8");

    expect(result.filePath).toContain("mock-erp-daily.csv");
    expect(csv).toContain("report_name,mock-erp-daily");
    expect(csv).toContain("Shop Alpha,2026-07-26,54320.2,108,9200.1,0.36,SKU-MACBOOK-PRO-14");
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/report-service.test.ts`
Expected: FAIL，因为 `ReportService` 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
import fs from "node:fs/promises";
import path from "node:path";
import type { ErpDailyReport } from "../providers/erp-data-provider";

export type ReportArtifact = {
  filePath: string;
  fileName: string;
};

type ReportInput = ErpDailyReport & {
  reportName: string;
  generatedAt: string;
};

export class ReportService {
  constructor(private readonly outputDir: string) {}

  async writeDailyReport(input: ReportInput): Promise<ReportArtifact> {
    await fs.mkdir(this.outputDir, { recursive: true });
    const fileName = `${input.reportName}.csv`;
    const filePath = path.join(this.outputDir, fileName);

    const lines = [
      `report_name,${input.reportName}`,
      `generated_at,${input.generatedAt}`,
      `total_sales,${input.summary.totalSales}`,
      `total_orders,${input.summary.totalOrders}`,
      `total_ad_spend,${input.summary.totalAdSpend}`,
      `average_gross_margin,${input.summary.averageGrossMargin}`,
      "",
      "shop_name,date,sales_amount,order_count,ad_spend,gross_margin,top_sku",
      ...input.records.map((record) =>
        [
          record.shopName,
          record.date,
          record.salesAmount,
          record.orderCount,
          record.adSpend,
          record.grossMargin,
          record.topSku,
        ].join(","),
      ),
    ];

    await fs.writeFile(filePath, `${lines.join("\n")}\n`, "utf8");
    return { filePath, fileName };
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/report-service.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/report-service.test.ts src/services/report-service.ts
git commit -m "feat: add csv report service"
```

### Task 3: 增加 ERP 飞书通知方法

**Files:**
- Modify: `src/adapters/feishu.ts`
- Modify: `tests/feishu-adapter.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
it("sends an ERP report summary message with owner mention", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce({
    ok: true,
    json: async () => ({
      ok: true,
    }),
  });

  const adapter = new FeishuAdapter(
    {
      appId: "app-id",
      appSecret: "secret",
      appToken: "token",
      tableId: "table-id",
      webhook: "https://example.com/webhook",
    },
    fetcher as typeof fetch,
  );

  await adapter.sendErpReport(
    "ou_123",
    "张三",
    "2026-07-26 运营日报",
    "/tmp/mock-erp-daily.csv",
    "总销售额 152340.5，订单数 328",
  );

  const call = fetcher.mock.calls[0];
  const body = JSON.parse(
    String((call?.[1] as RequestInit | undefined)?.body),
  ) as { content?: { text?: string } };

  expect(body.content?.text).toContain("2026-07-26 运营日报");
  expect(body.content?.text).toContain("总销售额 152340.5，订单数 328");
  expect(body.content?.text).toContain('<at user_id=\"ou_123\">张三</at>');
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/feishu-adapter.test.ts`
Expected: FAIL，因为 `sendErpReport` 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/feishu-adapter.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/feishu-adapter.test.ts src/adapters/feishu.ts
git commit -m "feat: add erp report notification message"
```

### Task 4: 增加 ERP 报表运行模式

**Files:**
- Modify: `src/runner.ts`
- Modify: `tests/runner.test.ts`

- [ ] **Step 1: 写失败测试**

```ts
it("runs the mock ERP report mode and sends a report", async () => {
  const sendErpReport = vi.fn().mockResolvedValue(undefined);
  const runner = createErpReportRunner(
    {
      getDailyReport: vi.fn().mockResolvedValue({
        summary: {
          totalSales: 152340.5,
          totalOrders: 328,
          totalAdSpend: 28120.3,
          averageGrossMargin: 0.34,
        },
        records: [],
      }),
    } as never,
    {
      writeDailyReport: vi.fn().mockResolvedValue({
        filePath: "/tmp/mock-erp-daily.csv",
        fileName: "mock-erp-daily.csv",
      }),
    } as never,
    {
      sendErpReport,
    } as never,
  );

  await runner({
    ownerOpenId: "ou_123",
    ownerDisplayName: "张三",
  });

  expect(sendErpReport).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npm test -- tests/runner.test.ts`
Expected: FAIL，因为 ERP 报表模式与辅助 runner 还不存在。

- [ ] **Step 3: 写最小实现**

```ts
type ErpReportOwner = {
  ownerOpenId: string;
  ownerDisplayName: string;
};

export function createErpReportRunner(
  provider: Pick<ErpDataProvider, "getDailyReport">,
  reportService: Pick<ReportService, "writeDailyReport">,
  feishuAdapter: Pick<FeishuAdapter, "sendErpReport">,
) {
  return async function runErpReport(owner: ErpReportOwner): Promise<void> {
    const report = await provider.getDailyReport();
    const reportTitle = `${new Date().toISOString().slice(0, 10)} 运营日报`;
    const artifact = await reportService.writeDailyReport({
      reportName: "mock-erp-daily",
      generatedAt: new Date().toISOString(),
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
```

```ts
if (mode === "erp-report") {
  const ownerOpenId = process.env.ERP_REPORT_OWNER_OPEN_ID ?? "";
  const ownerDisplayName = process.env.ERP_REPORT_OWNER_DISPLAY_NAME ?? "";
  if (!ownerOpenId) {
    throw new Error("ERP_REPORT_OWNER_OPEN_ID is required.");
  }

  const adapter = new FeishuAdapter({
    appId: config.feishuAppId,
    appSecret: config.feishuAppSecret,
    appToken: config.feishuAppToken,
    tableId: config.feishuTableId,
    webhook: config.feishuBotWebhook,
  });

  const reportRunner = createErpReportRunner(
    new MockErpDataProvider(),
    new ReportService(config.outputDir),
    adapter,
  );
  await reportRunner({ ownerOpenId, ownerDisplayName });
  return;
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm test -- tests/runner.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/runner.test.ts src/runner.ts src/providers/mock-erp-data-provider.ts src/services/report-service.ts
git commit -m "feat: add mock erp report runner"
```

### Task 5: 文档与全量验证

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 更新说明**

```md
## Mock ERP 报表

使用假数据生成运营报表并发送飞书通知：

```bash
ERP_REPORT_OWNER_OPEN_ID=ou_xxx \
ERP_REPORT_OWNER_DISPLAY_NAME=张三 \
npm exec tsx src/runner.ts erp-report
```

输出产物默认写入 `OUTPUT_DIR`，当前格式为 CSV。
```

- [ ] **Step 2: 运行完整验证**

Run: `npm test -- tests/mock-erp-data-provider.test.ts tests/report-service.test.ts tests/feishu-adapter.test.ts tests/runner.test.ts`
Expected: PASS

Run: `npm run build`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add README.md tests/mock-erp-data-provider.test.ts tests/report-service.test.ts tests/feishu-adapter.test.ts tests/runner.test.ts src/providers/erp-data-provider.ts src/providers/mock-erp-data-provider.ts src/services/report-service.ts src/runner.ts src/adapters/feishu.ts
git commit -m "docs: document mock erp reporting workflow"
```
