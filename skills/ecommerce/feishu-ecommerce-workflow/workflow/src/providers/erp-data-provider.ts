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
