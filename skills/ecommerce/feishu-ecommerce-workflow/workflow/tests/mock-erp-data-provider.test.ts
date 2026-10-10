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
