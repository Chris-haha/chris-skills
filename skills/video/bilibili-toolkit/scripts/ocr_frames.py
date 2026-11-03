# -*- coding: utf-8 -*-
"""视频抽帧 OCR 屏幕字幕 → 时间轴（用于校准 ASR 逐字稿）
用法: python ocr_frames.py <视频文件> [--step 3] [--conf 0.55] [--out 前缀]
输出: <out>.timeline.json（全部帧文本）+ <out>.dedup.txt（相邻去重，人读版）
要点：新闻播报/教程类视频多有内嵌字幕，OCR 抓到的就是 UP 主的"官方字幕"，
以它为基准修订 ASR 稿；置信度<conf 或长度<2 的行丢弃。
"""
import argparse, json, os, sys, time

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
sys.stdout.reconfigure(encoding="utf-8")

import av
from rapidocr_onnxruntime import RapidOCR

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--step", type=float, default=3, help="抽帧间隔秒")
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--out")
    a = ap.parse_args()
    out_prefix = a.out or (os.path.splitext(a.video)[0] + "_ocr")

    container = av.open(a.video)
    stream = container.streams.video[0]
    dur = float(container.duration) / 1e6
    print(f"video dur={dur:.1f}s step={a.step}s", flush=True)

    ocr = RapidOCR()
    t0 = time.time()
    results, target_t = [], 0.0
    container.seek(0)
    for frame in container.decode(stream):
        ft = float(frame.pts * stream.time_base)
        if ft + 1e-6 < target_t:
            continue
        res, _ = ocr(frame.to_ndarray(format="bgr24"))
        texts = [t.strip() for box, t, c in (res or []) if c and c >= a.conf and len(t.strip()) >= 2]
        if texts:
            results.append({"t": round(ft, 1), "texts": texts})
        target_t += a.step

    with open(out_prefix + ".timeline.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    seen, uniq = set(), []
    for r in results:
        key = " ".join(r["texts"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f"[{int(r['t'])//60:02d}:{int(r['t'])%60:02d}] " + " | ".join(r["texts"]))
    with open(out_prefix + ".dedup.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(uniq))
    print(f"frames~{int(dur/a.step)+1} kept={len(results)} uniq={len(uniq)} elapsed={time.time()-t0:.0f}s", flush=True)
    print("->", out_prefix + ".timeline.json / .dedup.txt", flush=True)

if __name__ == "__main__":
    main()
