from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import uuid
from collections import defaultdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "out"


def _now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _parse_relative_date(text: str, today: dt.date) -> tuple[str | None, bool]:
    if "今天" in text or "今日" in text:
        return today.isoformat(), True
    if "明天" in text:
        return (today + dt.timedelta(days=1)).isoformat(), True
    if "后天" in text:
        return (today + dt.timedelta(days=2)).isoformat(), True
    if "本周" in text or "这周" in text:
        return today.isoformat(), False
    match = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", text)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = today.year
        try:
            return dt.date(year, month, day).isoformat(), False
        except ValueError:
            return None, False
    return None, False


def _parse_time_hint(text: str) -> str | None:
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    match = re.search(r"(\d{1,2})点(?:半|(\d{1,2})分)?", text)
    if match:
        hour = int(match.group(1))
        minute = "30" if "半" in match.group(0) else f"{int(match.group(2) or 0):02d}"
        return f"{hour:02d}:{minute}"
    return None


def classify_note(text: str) -> dict[str, object]:
    normalized = _normalize(text)
    today = _now().date()
    due_date, exact_date_hint = _parse_relative_date(normalized, today)
    time_hint = _parse_time_hint(normalized)
    urgent_markers = ["马上", "立刻", "尽快", "现在", "今天", "别忘", "提醒我", "截止", "before", "urgent"]
    waiting_markers = ["等", "等待", "等他", "等她", "等对方", "确认后"]
    someday_markers = ["以后", "有空", "再说", "下次", "之后再看"]
    idea_markers = ["想到", "灵感", "也许", "备选", "新点子", "新想法"]
    review_markers = ["复盘", "周复盘", "日复盘", "review"]
    schedule_markers = ["会议", "约", "安排", "见面", "回访", "提醒", "日程"]

    lower = normalized.lower()
    status = "open"
    category = "task"
    needs_clarification = False
    reminder_needed = False
    escalation_level = "normal"

    if any(marker in normalized for marker in review_markers):
        category = "review"
    elif any(marker in normalized for marker in waiting_markers):
        category = "waiting"
        status = "waiting"
    elif any(marker in normalized for marker in someday_markers):
        category = "someday"
        status = "someday"
    elif any(marker in normalized for marker in idea_markers):
        category = "idea"
    elif any(marker in normalized for marker in schedule_markers) or due_date:
        category = "schedule"

    if due_date and category not in {"waiting", "someday"}:
        status = "scheduled"
        reminder_needed = True
    if any(marker in normalized for marker in urgent_markers):
        reminder_needed = True
        escalation_level = "high"
    if due_date is None and any(marker in normalized for marker in ["明天", "后天", "今天", "周", "月", "号", "点"]):
        needs_clarification = time_hint is None and not exact_date_hint
    if category == "idea" and not due_date:
        reminder_needed = False
    if category == "review":
        reminder_needed = True

    priority = "medium"
    if escalation_level == "high" or any(marker in normalized for marker in ["马上", "立刻", "尽快", "截止"]):
        priority = "high"
    elif category in {"someday", "idea"}:
        priority = "low"

    summary = normalized
    if summary.endswith("。"):
        summary = summary[:-1]

    reminder_at = None
    if due_date and time_hint:
        reminder_at = f"{due_date}T{time_hint}:00"
    elif due_date:
        reminder_at = f"{due_date}T09:00:00"

    if category in {"waiting", "someday"}:
        reminder_needed = False

    return {
        "id": f"note-{uuid.uuid4().hex[:10]}",
        "captured_at": _now().isoformat(timespec="seconds"),
        "source": "manual",
        "raw_text": text,
        "summary": summary,
        "category": category,
        "priority": priority,
        "due_at": due_date,
        "reminder_at": reminder_at,
        "status": status,
        "needs_clarification": needs_clarification,
        "reminder_needed": reminder_needed,
        "escalation_level": escalation_level,
        "tags": [],
    }


def capture_notes(notes: list[str]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    for note in notes:
        cleaned = _normalize(note)
        if not cleaned:
            continue
        fingerprint = cleaned.lower()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        items.append(classify_note(cleaned))
    return items


def _read_inbox(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf8")


def build_daily_summary(items: list[dict[str, object]]) -> str:
    today = [item for item in items if item.get("due_at") or item.get("escalation_level") == "high"]
    waiting = [item for item in items if item.get("category") == "waiting"]
    needs_clarification = [item for item in items if item.get("needs_clarification")]
    someday = [item for item in items if item.get("category") == "someday"]

    lines = ["# 今日整理", ""]
    lines.append("## 优先处理")
    if today:
        for item in today:
            lines.append(f"- [{item['priority']}] {item['summary']}")
    else:
        lines.append("- 今天没有明确优先事项。")

    lines.append("")
    lines.append("## 等待中")
    if waiting:
        for item in waiting:
            lines.append(f"- {item['summary']}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 待确认")
    if needs_clarification:
        for item in needs_clarification:
            lines.append(f"- {item['summary']}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 以后再说")
    if someday:
        for item in someday:
            lines.append(f"- {item['summary']}")
    else:
        lines.append("- 无")
    return "\n".join(lines)


def build_week_summary(items: list[dict[str, object]]) -> str:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in items:
        bucket = item.get("category", "task")
        grouped[str(bucket)].append(item)

    lines = ["# 本周整理", ""]
    for bucket in ("schedule", "task", "review", "waiting", "idea", "someday"):
        group = grouped.get(bucket, [])
        if not group:
            continue
        lines.append(f"## {bucket}")
        for item in group:
            suffix = f" ({item['due_at']})" if item.get("due_at") else ""
            lines.append(f"- {item['summary']}{suffix}")
        lines.append("")
    return "\n".join(lines).strip()


def build_review_summary(items: list[dict[str, object]]) -> str:
    total = len(items)
    scheduled = sum(1 for item in items if item.get("status") == "scheduled")
    clarification = sum(1 for item in items if item.get("needs_clarification"))
    waiting = sum(1 for item in items if item.get("category") == "waiting")
    return "\n".join(
        [
            "# 复盘",
            "",
            f"- 总条目数：{total}",
            f"- 已安排：{scheduled}",
            f"- 待确认：{clarification}",
            f"- 等待中：{waiting}",
        ]
    )


def build_reminder_payload(items: list[dict[str, object]]) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for item in items:
        if not item.get("reminder_needed"):
            continue
        title = str(item.get("summary", "待办提醒"))
        urgency = "high" if item.get("escalation_level") == "high" else "normal"
        payloads.append(
            {
                "id": item.get("id"),
                "title": title,
                "message": item.get("raw_text", title),
                "trigger_type": "time" if item.get("reminder_at") else "condition" if item.get("category") == "waiting" else "hybrid",
                "send_at": item.get("reminder_at") or item.get("due_at"),
                "lead_time_minutes": 0,
                "urgency": urgency,
                "channel": "external_mcp",
                "status": "pending",
                "source_id": item.get("id"),
                "source_text": item.get("raw_text"),
                "dedupe_key": _normalize(str(item.get("raw_text", ""))).lower(),
                "created_at": item.get("captured_at"),
                "condition": "waiting_for_reply" if item.get("category") == "waiting" else None,
                "suggested_channel": "external_mcp",
            }
        )
    return payloads


def _default_output_dir(args: argparse.Namespace) -> Path:
    return Path(args.output_dir or DEFAULT_OUTPUT_DIR)


def _load_notes_from_args(args: argparse.Namespace) -> list[str]:
    if args.input:
        return Path(args.input).read_text(encoding="utf8").splitlines()
    if args.text:
        return args.text.splitlines()
    return [line.rstrip("\n") for line in __import__("sys").stdin if line.strip()]


def _save_capture(output_dir: Path, items: list[dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "inbox.json", items)
    _write_text(output_dir / "capture.md", build_daily_summary(items))


def cmd_capture(args: argparse.Namespace) -> int:
    items = capture_notes(_load_notes_from_args(args))
    out_dir = _default_output_dir(args)
    _save_capture(out_dir, items)
    print(json.dumps({"items": len(items), "output_dir": str(out_dir)}, ensure_ascii=False, indent=2))
    return 0


def cmd_plan_today(args: argparse.Namespace) -> int:
    inbox = _read_inbox(Path(args.inbox))
    out_dir = _default_output_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_text(out_dir / "today.md", build_daily_summary(inbox))
    print(json.dumps({"output": str(out_dir / "today.md")}, ensure_ascii=False, indent=2))
    return 0


def cmd_plan_week(args: argparse.Namespace) -> int:
    inbox = _read_inbox(Path(args.inbox))
    out_dir = _default_output_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_text(out_dir / "week.md", build_week_summary(inbox))
    print(json.dumps({"output": str(out_dir / "week.md")}, ensure_ascii=False, indent=2))
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    inbox = _read_inbox(Path(args.inbox))
    out_dir = _default_output_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_text(out_dir / "review.md", build_review_summary(inbox))
    print(json.dumps({"output": str(out_dir / "review.md")}, ensure_ascii=False, indent=2))
    return 0


def cmd_prepare_reminders(args: argparse.Namespace) -> int:
    inbox = _read_inbox(Path(args.inbox))
    out_dir = _default_output_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_reminder_payload(inbox)
    _write_json(out_dir / "reminders.json", payload)
    print(json.dumps({"count": len(payload), "output": str(out_dir / "reminders.json")}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily schedule inbox helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture")
    capture.add_argument("--input")
    capture.add_argument("--text")
    capture.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    capture.set_defaults(func=cmd_capture)

    plan_today = subparsers.add_parser("plan-today")
    plan_today.add_argument("--inbox", required=True)
    plan_today.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    plan_today.set_defaults(func=cmd_plan_today)

    plan_week = subparsers.add_parser("plan-week")
    plan_week.add_argument("--inbox", required=True)
    plan_week.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    plan_week.set_defaults(func=cmd_plan_week)

    review = subparsers.add_parser("review")
    review.add_argument("--inbox", required=True)
    review.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    review.set_defaults(func=cmd_review)

    reminders = subparsers.add_parser("prepare-reminders")
    reminders.add_argument("--inbox", required=True)
    reminders.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    reminders.set_defaults(func=cmd_prepare_reminders)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
