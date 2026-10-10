# 飞书生图工作流 MVP

这个目录用于承载飞书生图工作流 MVP。当前已经支持：

- 读取飞书多维表格待处理任务
- 生成图片并打包 zip
- 回写任务状态
- 通过飞书机器人通知负责人
- 默认关闭的自动轮询执行
- 需要显式确认的人工重跑入口

## 环境要求

- Node.js 24 及以上
- npm 10 及以上

## 初始化

```bash
npm install
cp .env.example .env
```

然后在 `.env` 中填写飞书应用信息、表格信息和运行参数。

## 关键配置

- `IMAGE_PROVIDER=mock`：本地联调默认值，不消耗真实生图额度。
- `IMAGE_PROVIDER=openai`：使用真实生图服务。
- `OPENAI_API_KEY`：OpenAI 或兼容网关的 API Key。
- `OPENAI_BASE_URL`：只有在接第三方 OpenAI 兼容网关时才需要配置。
- `OPENAI_IMAGE_MODEL`：兼容网关使用的模型名，默认是 `gpt-image-1`。
- `OUTPUT_DIR`：产物输出目录，会被解析成绝对路径。
- `RETENTION_DAYS`：产物保留天数，必须是正整数。
- `AUTO_RUN_ENABLED=false`：默认关闭自动轮询，防止忘记关闭后重复执行。
- `AUTO_RUN_INTERVAL_MINUTES=10`：自动轮询间隔，单位是分钟。

如果直连 OpenAI，通常只需要：

```bash
IMAGE_PROVIDER=openai
OPENAI_API_KEY=<your-openai-or-gateway-api-key>
```

如果使用第三方 OpenAI 兼容网关，还需要补充：

```bash
OPENAI_BASE_URL=<your-openai-compatible-base-url>
OPENAI_IMAGE_MODEL=gpt-image-2
```

## 常用命令

```bash
npm test
npm run build
```

## 运行方式

单次执行：

```bash
npm exec tsx src/runner.ts
```

开启自动轮询：

```bash
AUTO_RUN_ENABLED=true
AUTO_RUN_INTERVAL_MINUTES=10
npm exec tsx src/runner.ts run-loop
```

人工重跑已完成任务：

```bash
npm exec tsx src/runner.ts rerun-task iphone-pro-test --confirm-rerun-completed
```

如果不带 `--confirm-rerun-completed`，已完成任务不会被重跑。

## Mock ERP 报表

使用假数据生成运营报表并发送飞书通知：

```bash
ERP_REPORT_OWNER_OPEN_ID=ou_xxx \
ERP_REPORT_OWNER_DISPLAY_NAME=张三 \
npm exec tsx src/runner.ts erp-report
```

输出产物默认写入 `OUTPUT_DIR`，当前格式为 CSV。
