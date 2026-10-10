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
    expect(csv).toContain(
      "Shop Alpha,2026-07-26,54320.2,108,9200.1,0.36,SKU-MACBOOK-PRO-14",
    );
  });
});
