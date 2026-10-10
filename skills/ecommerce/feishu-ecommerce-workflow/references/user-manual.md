# 飞书电商工作流使用说明

## 1. 安装后直接运行

成品 skill 已经包含完整的 `workflow/` 目录，里面有 `package.json`、`src/`、测试、构建配置和 `.env.example`。用户不需要准备或查找原项目路径。

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/feishu-ecommerce-workflow"
python3 "$SKILL_DIR/scripts/run_workflow.py" init
```

wrapper 会在 `${CODEX_HOME:-$HOME/.codex}/feishu-ecommerce-workflow-runtime` 建立本机运行目录，并把 `.env.example` 复制为 `.env`。如需换目录，可设置：

```bash
export FEISHU_ECOMMERCE_RUNTIME_DIR="$HOME/feishu-ecommerce-workflow-runtime"
```

已有完整 `mvp-workflow` 项目时，可以继续使用：

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" doctor --workflow-dir /path/to/mvp-workflow
```

首次执行测试或构建时，如果本机没有依赖，wrapper 会在本地运行目录执行 `npm install`。

## 2. 配置 `.env`

编辑本机运行目录中的 `.env`。模板已经预置以下配置项：

```dotenv
FEISHU_APP_ID=<your-feishu-app-id>
FEISHU_APP_SECRET=<your-feishu-app-secret>
FEISHU_APP_TOKEN=<your-bitable-app-token>
FEISHU_TABLE_ID=<your-bitable-table-id>
FEISHU_BOT_WEBHOOK=<your-feishu-bot-webhook>
OUTPUT_DIR=./data
RETENTION_DAYS=7
AUTO_RUN_ENABLED=false
AUTO_RUN_INTERVAL_MINUTES=10
IMAGE_PROVIDER=mock

# 使用真实生图时再填写
# OPENAI_API_KEY=<your-openai-or-gateway-api-key>
# OPENAI_BASE_URL=<your-openai-compatible-base-url>
# OPENAI_IMAGE_MODEL=<your-image-model-name>

# 运营日报和创建测试任务按需填写
# ERP_REPORT_OWNER_OPEN_ID=<owner-open-id>
# ERP_REPORT_OWNER_DISPLAY_NAME=<owner-display-name>
# SEED_OWNER_OPEN_ID=<owner-open-id>
# SEED_OWNER_DISPLAY_NAME=<owner-display-name>
```

`IMAGE_PROVIDER=mock` 是默认联调模式，不调用真实生图接口。确认飞书流程可用后，再改为 `IMAGE_PROVIDER=openai` 并填写生图服务配置。直连 OpenAI 时通常只需要 `OPENAI_API_KEY`；第三方兼容网关还需要 `OPENAI_BASE_URL` 和 `OPENAI_IMAGE_MODEL`。

配置完成后检查：

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" doctor
```

`doctor` 会打印配置摘要，并遮蔽密钥。未填写的占位符会被视为缺失配置。

## 3. 常用流程

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" test
python3 "$SKILL_DIR/scripts/run_workflow.py" build
python3 "$SKILL_DIR/scripts/run_workflow.py" run-once
```

`run-once` 处理飞书多维表中状态为 `待处理` 或 `失败待重试` 的任务，依次生成图片、归档 zip、回写状态并发送机器人消息。

需要持续轮询时：

```bash
AUTO_RUN_ENABLED=true python3 "$SKILL_DIR/scripts/run_workflow.py" run-loop
```

## 4. 多维表字段

表格建议包含以下字段：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `task_seq` | 数字 | 任务顺序号 |
| `task_id` | 文本 | 任务唯一 ID |
| `product_name` | 文本 | 产品名称 |
| `owner_open_id` | 文本 | 负责人 open_id |
| `owner_display_name` | 文本 | 负责人姓名 |
| `prompt_template` | 文本 | 生图提示词 |
| `image_count` | 数字 | 图片数量 |
| `retry_count` | 数字 | 重试次数 |
| `task_status` | 单选或文本 | `待处理`、`失败待重试` 等状态 |
| `status_note` | 文本 | 失败原因或产物路径 |
| `image_date` | 日期或文本 | 生图日期 |

## 5. 配置项来源

- `FEISHU_APP_ID`、`FEISHU_APP_SECRET`：飞书开放平台应用详情。
- `FEISHU_APP_TOKEN`、`FEISHU_TABLE_ID`：多维表 URL 或表格详情。
- `FEISHU_BOT_WEBHOOK`：群自定义机器人设置。
- `owner_open_id`：飞书用户 open_id，不能用手机号、union_id 替代。
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL`：所选生图服务提供方。

飞书应用需要具备读取和写入多维表、获取 tenant access token、按 open_id 查询用户名称等权限。表格来自 wiki 时，还需要相应节点访问权限。

## 6. 其他命令

创建测试任务：

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" seed-task
```

生成 mock ERP 日报：

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" erp-report
```

重跑已完成任务必须显式确认：

```bash
python3 "$SKILL_DIR/scripts/run_workflow.py" rerun-task <task_id> --confirm-rerun-completed
```

## 7. 常见问题

`doctor` 报缺少配置：编辑本机 runtime 的 `.env`，不要编辑 zip 内文件。

`npm` 或 Node.js 不可用：安装 Node.js 18 或更高版本后重新执行命令。

飞书返回权限错误：按错误信息在开放平台开通权限，并确认应用已发布或重新授权。

机器人没有艾特负责人：检查机器人已加入群聊，且 `owner_open_id` 是用户的 open_id。

真实生图失败：先切回 `IMAGE_PROVIDER=mock` 验证飞书读表、回写和通知链路，再检查模型名、base URL、响应格式和服务额度。
