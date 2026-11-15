from pathlib import Path
import argparse, json

p = argparse.ArgumentParser(description="Initialize an empty Bilibili analyst workspace without overwriting existing files.")
p.add_argument("workspace", type=Path)
a = p.parse_args()
target = a.workspace.expanduser().resolve()
for d in ("data", "reports", "transcripts", "media"):
    (target / d).mkdir(parents=True, exist_ok=True)
config = {"accounts": [], "blacklist": [], "timezone": "Asia/Shanghai", "window_end_local": "09:00", "notes": "请按用户要求填写账号，身份应记录 MID 和核验来源。"}
path = target / "watchlist.json"
try:
    with path.open("x", encoding="utf-8") as f: json.dump(config, f, ensure_ascii=False, indent=2)
    print("created", path)
except FileExistsError:
    print("preserved", path)
print("Workspace:", target)
