# -*- coding: utf-8 -*-
"""B站视频元数据+章节解析：支持 bvid / 完整URL / b23.tv 短链
用法: python bili_meta.py <bvid或URL>
输出: JSON（含 cid/mid/season_id/章节），供下游脚本使用
"""
import json, re, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def get(url, referer="https://www.bilibili.com/"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8")

def resolve_bvid(arg):
    m = re.search(r"BV\w+", arg)
    if m:
        return m.group(0)
    # b23.tv 等短链：跟随重定向拿最终 URL
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(arg, headers={"User-Agent": UA})
    try:
        opener.open(req, timeout=15)
        raise ValueError("短链未重定向，无法解析")
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
    m = re.search(r"BV\w+", loc)
    if m:
        return m.group(0)
    m = re.search(r"av(\d+)", loc, re.I)
    if m:  # av号转bvid走view接口
        return int(m.group(1))
    raise ValueError("无法从链接解析出 bvid: " + loc)

def main():
    arg = sys.argv[1]
    bvid = resolve_bvid(arg)
    q = f"bvid={bvid}" if isinstance(bvid, str) else f"aid={bvid}"
    view = json.loads(get(f"https://api.bilibili.com/x/web-interface/view?{q}"))
    if view.get("code") != 0:
        print("view error:", view.get("code"), view.get("message")); sys.exit(1)
    d = view["data"]
    bvid = d["bvid"]
    try:
        player = json.loads(get(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={d['cid']}"))
        chapters = [ { "from": c["from"], "to": c["to"], "title": c["content"] }
                     for c in (player.get("data", {}).get("view_points") or []) ]
    except Exception:
        chapters = []
    out = {
        "bvid": d["bvid"], "aid": d["aid"], "cid": d["cid"],
        "title": d["title"], "desc": d["desc"],
        "pubdate": d["pubdate"], "duration": d["duration"],
        "owner": {"mid": d["owner"]["mid"], "name": d["owner"]["name"]},
        "season_id": (d.get("ugc_season") or {}).get("id"),
        "stat": {"view": d["stat"]["view"], "like": d["stat"]["like"], "danmaku": d["stat"]["danmaku"]},
        "chapters": chapters,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
