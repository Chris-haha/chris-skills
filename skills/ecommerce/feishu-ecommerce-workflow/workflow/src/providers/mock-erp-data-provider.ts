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
