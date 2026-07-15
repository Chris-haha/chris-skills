# 日程整理 Skill 规格

## 目标

把零散的文本记录整理成结构化 inbox，再生成日程、代办和提醒 payload。

## 核心规则

1. 只处理纯文本输入
2. 先收集，再 triage，再生成计划和提醒
3. 不替用户编日期，含糊信息必须标记待确认
4. 紧急事项可以升级提醒，但发送动作交给外部 MCP
5. 第一数据源固定为本地 Markdown / JSON

## 输出形态

- `inbox.json`：结构化条目
- `today.md`：今日计划
- `week.md`：周计划
- `review.md`：日/周复盘
- `reminders.json`：给外部 MCP 的提醒 payload

## 提醒 Payload 规范

`reminders.json` 的每一项建议包含以下字段：

- `id`：唯一标识
- `title`：提醒标题
- `message`：提醒正文
- `trigger_type`：`time` / `condition` / `hybrid`
- `send_at`：定时发送时间
- `lead_time_minutes`：提前提醒分钟数
- `urgency`：`low` / `normal` / `high`
- `channel`：目标渠道，例如 `qclaw` 或 `feishu`
- `status`：`pending` / `sent` / `skipped`
- `source_text`：原始文本
- `dedupe_key`：去重键
- `created_at`：创建时间
- `condition`：条件触发时使用的条件名

## 状态

- `open`
- `needs_clarification`
- `waiting`
- `someday`
- `scheduled`
- `done`

## 分类

- `schedule`
- `task`
- `reminder`
- `idea`
- `waiting`
- `someday`
- `review`

## 运行流程

1. 你把碎片文本交给 Codex 或直接写入输入文件。
2. skill 把文本整理成 `inbox.json`。
3. skill 从 `inbox.json` 生成 `today.md`、`week.md`、`review.md` 和 `reminders.json`。
4. QClaw / 飞书读取 `reminders.json`。
5. 到了 `send_at`，或者条件满足时，外部自动化调用 MCP 发消息给你。
6. 发送完成后，把对应条目标记为 `sent`。
