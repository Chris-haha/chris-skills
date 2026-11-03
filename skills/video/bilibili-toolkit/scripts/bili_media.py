# -*- coding: utf-8 -*-
"""下载B站视频流：音频（转写用，最低码率）+ 可选480p视频（OCR校准用）
用法: python bili_media.py <bvid> [--cid CID] [--video] [--out 输出目录]
依赖 bili_meta 同款直连 view 接口；下载必须带 Referer 和 Range 头
"""
import argparse, json, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode())

def dl(url, out):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.bilibili.com/", "Range": "bytes=0-"})
    data = urllib.request.urlopen(req, timeout=300).read()
    with open(out, "wb") as f:
        f.write(data)
    print("saved:", out, round(len(data) / 1048576, 2), "MB")
    return data[:12].hex()  # 文件头，供格式校验（ftyp=66747970）

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bvid")
    ap.add_argument("--cid", type=int)
    ap.add_argument("--video", action="store_true", help="同时下载480p视频流（OCR用）")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    view = get(f"https://api.bilibili.com/x/web-interface/view?bvid={a.bvid}")
    if view.get("code") != 0:
        print("view error:", view.get("code"), view.get("message")); sys.exit(1)
    d = view["data"]
    cid = a.cid or d["cid"]

    play = get(f"https://api.bilibili.com/x/player/playurl?bvid={a.bvid}&cid={cid}&fnval=16&qn=64")
    if play.get("code") != 0:
        print("playurl error:", play.get("code")); sys.exit(1)
    dash = play["data"].get("dash") or {}

    audios = dash.get("audio") or []
    if not audios:
        print("无音频流（可能为纯音频稿或需登录）"); sys.exit(1)
    # 最低码率音频足够转写（普通话口播），文件小下载快
    head = dl(min(audios, key=lambda x: x.get("bandwidth") or 10**9)["baseUrl"],
              a.out.rstrip("/\\") + f"/{a.bvid}_audio.m4s")
    if not head.startswith("0000002066747970"):
        print("警告：音频文件头不是 ftyp，文件可能异常:", head)

    if a.video:
        videos = dash.get("video") or []
        if videos:
            # OCR 需要 480p（id==32）里带宽最低的；没有就取全局最低
            v480 = [v for v in videos if v.get("id") == 32]
            pick = min(v480 or videos, key=lambda x: x.get("bandwidth") or 10**9)
            dl(pick["baseUrl"], a.out.rstrip("/\\") + f"/{a.bvid}_video.m4s")

if __name__ == "__main__":
    main()
