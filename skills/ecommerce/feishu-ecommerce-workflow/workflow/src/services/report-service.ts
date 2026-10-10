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

    return {
      filePath,
      fileName,
    };
  }
}
