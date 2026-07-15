from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "schedule_inbox.py"
SPEC = importlib.util.spec_from_file_location("schedule_inbox", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_capture_notes_classifies_and_deduplicates():
    items = MODULE.capture_notes(
        [
            "明天 9 点和小王确认方案，记得提醒我",
            "明天 9 点和小王确认方案，记得提醒我",
            "先别回这条，等对方确认后再跟进",
        ]
    )

    assert len(items) == 2
    assert items[0]["category"] in {"schedule", "task"}
    assert items[0]["reminder_needed"] is True
    assert items[1]["category"] == "waiting"
    assert items[1]["status"] == "waiting"


def test_capture_notes_marks_ambiguous_time_for_clarification():
    item = MODULE.classify_note("周五约一下，但时间没定")

    assert item["needs_clarification"] is True
    assert item["status"] in {"open", "scheduled"}


def test_build_reminder_payload_only_includes_reminder_items():
    items = MODULE.capture_notes(
        [
            "今天 14:00 提醒我发预算给团队",
            "以后再想这个选题方向",
        ]
    )

    payload = MODULE.build_reminder_payload(items)

    assert len(payload) == 1
    assert payload[0]["urgency"] == "high"
    assert payload[0]["suggested_channel"] == "external_mcp"


def test_cli_capture_writes_expected_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_file = tmp_path / "notes.txt"
    input_file.write_text("明天 9 点和小王确认方案，记得提醒我\n", encoding="utf8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(
        "sys.argv",
        [
            "schedule_inbox.py",
            "capture",
            "--input",
            str(input_file),
            "--output-dir",
            str(out_dir),
        ],
    )

    assert MODULE.main() == 0
    assert (out_dir / "inbox.json").exists()
    assert (out_dir / "capture.md").exists()
    payload = json.loads((out_dir / "inbox.json").read_text(encoding="utf8"))
    assert payload[0]["reminder_needed"] is True
