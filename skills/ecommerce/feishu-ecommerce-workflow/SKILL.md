---
name: feishu-ecommerce-workflow
description: Use when running or onboarding the bundled Feishu ecommerce automation, including Bitable image-generation tasks, OpenAI-compatible image gateways, owner mentions, safe polling, manual reruns, and mock ERP reports.
---

# Feishu Ecommerce Workflow

这个 skill 是可移植的完整工作流包。安装后自带 `workflow/` 运行时，不需要用户另外寻找原电脑上的 `mvp-workflow` 项目。

## 首次使用

直接使用 skill 目录里的 wrapper：

```bash
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py init
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py doctor
```

首次运行会把内置运行时复制到 `~/.codex/feishu-ecommerce-workflow-runtime`，并创建本地 `.env`。用户只需编辑这个 `.env`，填写自己的飞书和生图服务配置。配置不会写入 skill 包。

也可以通过 `FEISHU_ECOMMERCE_RUNTIME_DIR` 指定本地运行目录，或通过 `--workflow-dir` 使用已有的兼容 `mvp-workflow` 项目。

## 配置

内置 `.env.example` 已预置全部配置项。默认 `IMAGE_PROVIDER=mock`，用于测试流程，不调用真实生图服务。

需要用户按实际服务填写：

- `FEISHU_APP_ID`、`FEISHU_APP_SECRET`
- `FEISHU_APP_TOKEN`、`FEISHU_TABLE_ID`
- `FEISHU_BOT_WEBHOOK`
- 使用真实生图时的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL`
- 发送运营日报或创建测试任务时使用的负责人配置

运行参数已经给出安全默认值：`OUTPUT_DIR=./data`、`RETENTION_DAYS=7`、`AUTO_RUN_ENABLED=false`、`AUTO_RUN_INTERVAL_MINUTES=10`。

配置完成后执行：

```bash
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py doctor
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py test
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py build
```

## 常用命令

```bash
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py run-once
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py erp-report
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py seed-task
python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py rerun-task <task_id> --confirm-rerun-completed
AUTO_RUN_ENABLED=true python3 /path/to/feishu-ecommerce-workflow/scripts/run_workflow.py run-loop
```

`run-once` 会读取飞书多维表中的 `待处理` 或 `失败待重试` 任务，生成图片、打包 zip、回写状态并发送机器人通知。测试阶段先保持 `IMAGE_PROVIDER=mock`。

## 安全边界

- skill 只分发源码、依赖清单和配置模板，不分发 `node_modules`、输出图片、构建产物或本地 `.env`。
- 用户配置保存在本机运行目录的 `.env`，wrapper 会保留已有 `.env`，不会用模板覆盖它。
- `AUTO_RUN_ENABLED` 默认关闭。
- 已完成任务只有在显式传入 `--confirm-rerun-completed` 时才会重跑。

详细字段、飞书权限和故障排查见 `references/user-manual.md`。
