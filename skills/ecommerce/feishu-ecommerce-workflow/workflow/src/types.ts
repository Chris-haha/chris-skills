export type TaskStatus =
  | "待处理"
  | "排队中"
  | "生成中"
  | "打包中"
  | "发送中"
  | "已完成"
  | "失败待重试"
  | "人工介入";

export type ImageTask = {
  recordId: string;
  taskSeq: number;
  taskId: string;
  productName: string;
  ownerOpenId: string;
  ownerDisplayName: string;
  promptTemplate: string;
  imageCount: number;
  retryCount: number;
  status: TaskStatus;
};

export type GeneratedImage = {
  fileName: string;
  mimeType: "image/png";
  bytes: Buffer;
};
