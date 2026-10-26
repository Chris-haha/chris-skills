from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


EXTRACTOR_PATH = Path(
    os.environ.get('MEDIA_URLS_EXTRACTOR_PATH', str(Path(__file__).resolve().with_name('extract_video.py')))
).expanduser()
URL_PATTERN = re.compile(r"https?://[^\s<>\"'`)\]}）】、，。！？；]+")
FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
REQUIRED_OUTPUT_FILES = [
    "metadata.json",
    "transcript.txt",
    "transcript-cleaned.txt",
    "source-url.txt",
    "README.md",
]


def extract_urls_from_markdown(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0).rstrip('.,;:!?') for match in URL_PATTERN.finditer(text)))


def resolve_input_file(input_path: Path) -> Path:
    input_path = input_path.expanduser()
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件或目录不存在: {input_path}")
    if not input_path.is_dir():
        return input_path
    candidates = sorted(p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in {'.txt', '.md'})
    if not candidates:
        raise ValueError(f"目录中没有 .txt 或 .md 链接文件，请新建文件并一行一条放入视频链接: {input_path}")
    if len(candidates) > 1:
        names = '、'.join(p.name for p in candidates)
        raise ValueError(f"目录中有多个候选链接文件，请用 --input 指定其中一个文件: {names}")
    return candidates[0]


def validate_urls(urls: list[str]) -> list[str]:
    unique = list(dict.fromkeys(url.strip() for url in urls if url.strip()))
    if not unique:
        raise ValueError("未找到视频链接；请直接提供链接，或在 UTF-8 文本文件中一行放一条链接")
    for url in unique:
        parsed = urlsplit(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or any(c.isspace() for c in url):
            raise ValueError(f"视频链接需为完整的 http/https URL: {url}")
    return unique


def sanitize_path_component(text: str) -> str:
    cleaned = FORBIDDEN_CHARS.sub("-", str(text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"-+", "-", cleaned).strip(" .-")
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', cleaned, re.I):
        cleaned = '_' + cleaned
    if len(cleaned.encode('utf8')) > 180:
        suffix = hashlib.sha256(cleaned.encode('utf8')).hexdigest()[:8]
        cleaned = cleaned.encode('utf8')[:160].decode('utf8', errors='ignore').rstrip(' .-') + '-' + suffix
    return cleaned or "unknown"


def clean_transcript(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def validate_paths(input_path: Path, output_dir: Path) -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
    if input_path.is_dir():
        raise IsADirectoryError(f"输入路径不能是目录: {input_path}")
    output_dir.mkdir(parents=True, exist_ok=True)


def append_run_log(output_dir: Path, message: str) -> None:
    log_path = output_dir / "run.log"
    with log_path.open("a", encoding="utf8") as handle:
        handle.write(f"{message}\n")


def is_archive_complete(item_dir: Path) -> bool:
    return all((item_dir / name).exists() for name in REQUIRED_OUTPUT_FILES)


def ensure_unique_item_dir(base_dir: Path, author: str, title: str, source_url: str, index: int) -> Path:
    author_dir = base_dir / sanitize_path_component(author or "unknown-author")
    title_name = sanitize_path_component(title or f"unknown-video-{index}")
    candidate = author_dir / title_name

    if not candidate.exists():
        return candidate

    source_file = candidate / "source-url.txt"
    if source_file.exists() and source_file.read_text(encoding="utf8").strip() == source_url.strip():
        return candidate

    suffix = 2
    while True:
        variant = author_dir / f"{title_name}-{suffix}"
        if not variant.exists():
            return variant
        source_file = variant / "source-url.txt"
        if source_file.exists() and source_file.read_text(encoding="utf8").strip() == source_url.strip():
            return variant
        suffix += 1


def write_archive_files(base_dir: Path, source_url: str, result: dict[str, object], index: int) -> Path:
    author = str(result.get("author", "")).strip() or "unknown-author"
    title = str(result.get("title", "")).strip() or f"unknown-video-{index}"
    transcript = str(result.get("subtitle_text", "")).strip()
    item_dir = ensure_unique_item_dir(base_dir, author, title, source_url, index)
    item_dir.mkdir(parents=True, exist_ok=True)

    result = dict(result)
    if result.get('frames'):
        frames = []
        for position, frame in enumerate(result['frames'], start=1):
            source = Path(frame['path'])
            destination = item_dir / 'frames' / f"{position:04d}{source.suffix or '.jpg'}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            frames.append(dict(frame, path=destination.relative_to(item_dir).as_posix()))
        result['frames'] = frames

    (item_dir / "source-url.txt").write_text(f"{source_url.strip()}\n", encoding="utf8")
    (item_dir / "metadata.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf8",
    )
    (item_dir / "transcript.txt").write_text(f"{transcript}\n" if transcript else "", encoding="utf8")
    (item_dir / "transcript-cleaned.txt").write_text(
        f"{clean_transcript(transcript)}\n" if transcript else "",
        encoding="utf8",
    )
    (item_dir / "README.md").write_text(
        build_readme(author=author, title=title, source_url=source_url, result=result),
        encoding="utf8",
    )
    return item_dir


def build_readme(author: str, title: str, source_url: str, result: dict[str, object]) -> str:
    platform = str(result.get("platform", "")).strip()
    duration = str(result.get("duration", "")).strip()
    url = str(result.get("url", "")).strip() or source_url.strip()
    description = str(result.get("description", "")).strip()
    lines = [
        f"# {title}",
        "",
        f"- 博主：{author}",
        f"- 平台：{platform}" if platform else "- 平台：",
        f"- 时长：{duration}" if duration else "- 时长：",
        f"- 原链接：{source_url.strip()}",
        f"- 规范链接：{url}",
    ]
    if description:
        lines.extend(["", "## 描述", "", description])
    return "\n".join(lines) + "\n"


def parse_extractor_output(stdout: str) -> dict[str, object]:
    start = stdout.find("{")
    if start == -1:
        raise ValueError("Extractor did not return JSON output")
    return json.loads(stdout[start:])


def run_extractor(source_url: str, python_bin: str, extractor_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        [python_bin, str(extractor_path), source_url],
        capture_output=True,
        text=True,
        encoding="utf8",
        env=dict(os.environ, PYTHONUTF8="1"),
        check=False,
    )
    try:
        result = parse_extractor_output(completed.stdout)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(completed.stderr.strip() or "Extractor did not return valid JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Extractor must return a JSON object")
    if completed.returncode != 0 or result.get("error"):
        raise RuntimeError(str(result.get("error") or completed.stderr.strip() or "Extractor failed"))
    if not str(result.get("subtitle_text") or "").strip():
        raise ValueError("解析器没有返回有效文字稿，未标记为归档成功")
    return result


def batch_archive_media_urls(
    input_path: Path | None,
    output_dir: Path,
    python_bin: str,
    extractor_path: Path,
    retries: int = 1,
    skip_existing: bool = True,
    urls: list[str] | None = None,
) -> dict[str, object]:
    if (input_path is None) == (urls is None):
        raise ValueError("请选择直接链接或链接文件其中一种输入方式")
    if input_path is not None:
        input_path = resolve_input_file(input_path)
        try:
            urls = extract_urls_from_markdown(input_path.read_text(encoding="utf-8-sig"))
        except UnicodeError as exc:
            raise ValueError("链接文件需使用 UTF-8 编码，一行放一条视频链接") from exc
    urls = validate_urls(urls or [])
    output_dir = output_dir.expanduser()
    if input_path is not None:
        validate_paths(input_path, output_dir)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, object]] = []
    successes: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    append_run_log(output_dir, f"START total_urls={len(urls)} input={input_path or 'direct-urls'}")

    for index, source_url in enumerate(urls, start=1):
        append_run_log(output_dir, f"PROCESS index={index} url={source_url}")
        try:
            guessed_item_dir = None
            if skip_existing:
                for author_dir in output_dir.iterdir():
                    if not author_dir.is_dir():
                        continue
                    for item_dir in author_dir.iterdir():
                        if not item_dir.is_dir():
                            continue
                        source_file = item_dir / "source-url.txt"
                        if source_file.exists() and source_file.read_text(encoding="utf8").strip() == source_url.strip():
                            guessed_item_dir = item_dir
                            break
                    if guessed_item_dir:
                        break
                if guessed_item_dir and is_archive_complete(guessed_item_dir):
                    skipped.append({"source_url": source_url, "path": str(guessed_item_dir)})
                    append_run_log(output_dir, f"SKIP index={index} path={guessed_item_dir}")
                    continue

            last_error: Exception | None = None
            result: dict[str, object] | None = None
            for attempt in range(1, retries + 2):
                try:
                    result = run_extractor(source_url, python_bin, extractor_path)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    append_run_log(output_dir, f"RETRY index={index} attempt={attempt} error={exc}")
            if result is None:
                assert last_error is not None
                raise last_error
            if result.get("error"):
                raise RuntimeError(str(result["error"]))
            item_dir = write_archive_files(output_dir, source_url, result, index)
            successes.append(
                {
                    "source_url": source_url,
                    "author": result.get("author", ""),
                    "title": result.get("title", ""),
                    "path": str(item_dir),
                }
            )
            append_run_log(output_dir, f"SUCCESS index={index} path={item_dir}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"source_url": source_url, "reason": str(exc)})
            append_run_log(output_dir, f"FAIL index={index} url={source_url} error={exc}")

    failures_path = output_dir / "failures.json"
    failures_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    summary = {
        "total": len(urls),
        "success": len(successes),
        "failure": len(failures),
        "skipped": len(skipped),
        "failures_path": str(failures_path),
        "items": successes,
        "skipped_items": skipped,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    append_run_log(
        output_dir,
        f"END total={summary['total']} success={summary['success']} failure={summary['failure']} skipped={summary['skipped']}",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="直接提供视频链接，或从用户指定的文件/目录读取链接并批量归档")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="任意路径的 UTF-8 链接文件；目录下只有一个 .txt/.md 时可直接指定目录")
    source.add_argument("--url", action="append", help="直接提供一个视频链接；多个链接重复使用 --url")
    parser.add_argument("--output-dir", required=True, help="本次归档的输出目录")
    parser.add_argument("--config", help="本机 JSON 配置文件；相对工具/模型路径相对于此文件")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--extractor-path", default=str(EXTRACTOR_PATH))
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--no-skip-existing", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        from runtime import load_config
        if args.config:
            os.environ['MEDIA_URLS_CONFIG'] = str(Path(args.config).expanduser().absolute())
        load_config()
        if args.no_skip_existing:
            os.environ['MEDIA_URLS_BYPASS_CACHE'] = '1'
        summary = batch_archive_media_urls(
            input_path=Path(args.input) if args.input else None,
            output_dir=Path(args.output_dir),
            python_bin=args.python_bin,
            extractor_path=Path(args.extractor_path).expanduser(),
            retries=max(args.retries, 0),
            skip_existing=not args.no_skip_existing,
            urls=args.url,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary['failure'] else 0


if __name__ == "__main__":
    raise SystemExit(main())
