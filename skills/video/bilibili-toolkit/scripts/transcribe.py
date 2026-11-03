# -*- coding: utf-8 -*-
"""faster-whisper 本地转写 B 站音频 → 带时间戳逐字稿
用法: python transcribe.py <音频文件> [--model small|medium|large-v3] [--prompt 热词] [--out 输出.txt]
环境坑（勿改）：
  - av 必须锁 16.1.0（av 19 删了 metadata_errors，faster-whisper 1.2.1 直接崩）
  - HF_ENDPOINT=hf-mirror + HF_HUB_DISABLE_XET=1（否则 Xet 直连 401）
  - 模型缓存于 ~/.cache/huggingface，重复用不重下
"""
import argparse, os, sys, time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
sys.stdout.reconfigure(encoding="utf-8")

from faster_whisper import WhisperModel

def fmt(t):
    m, s = divmod(int(t), 60)
    return f"{m:02d}:{s:02d}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default="small", choices=["small", "medium", "large-v3"])
    ap.add_argument("--prompt", default="", help="专有名词热词，逗号分隔，抑制同音错误")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--out")
    a = ap.parse_args()

    t0 = time.time()
    print(f"loading model {a.model}(int8) via {os.environ['HF_ENDPOINT']}", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    print("model loaded", round(time.time() - t0, 1), "s", flush=True)

    kw = dict(language=a.lang, beam_size=5, best_of=5, temperature=0,
              vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
    if a.prompt:
        kw["initial_prompt"] = a.prompt
    segments, info = model.transcribe(a.audio, **kw)
    print("lang:", info.language, round(info.language_probability, 2), flush=True)

    lines = []
    for seg in segments:
        line = f"[{fmt(seg.start)} -> {fmt(seg.end)}] {seg.text.strip()}"
        print(line, flush=True)
        lines.append(line)

    out = a.out or (os.path.splitext(a.audio)[0] + f"_transcript_{a.model}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("DONE segments:", len(lines), "elapsed:", round(time.time() - t0, 1), "s ->", out, flush=True)

if __name__ == "__main__":
    main()
