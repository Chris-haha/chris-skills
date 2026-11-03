---
name: bilibili-toolkit
description: B站(bilibili)视频解析工具箱：解析视频链接/元数据/章节、提取视频口播逐字稿（音频下载+faster-whisper本地转写+OCR屏幕字幕校准，无需B站登录）、批量获取UP主/博主全部视频链接清单。当用户提到 B站/bilibili/b23.tv 链接解析、视频文字稿/逐字稿/字幕/口播内容提取、某个UP主全部视频/投稿列表/最近N天视频、视频本地转写 时使用；即使用户只贴一个 B 站链接问"这视频说了什么"也应触发。
---

# Bilibili Toolkit

三大任务，先看路由表再动手。所有脚本在本 skill 的 `scripts/` 下，用 Python 3.12 venv 运行（见「环境」）。

| 用户要什么 | 走哪条路 |
|---|---|
| 解析链接/这是什么视频 | 任务A：`bili_meta.py` |
| 视频口播逐字稿（文字稿原文） | 任务B：meta → media → transcribe →（可选）ocr 校准 |
| UP主全部/最近N天视频链接 | 任务C：读 `references/up-all-videos.md` 后执行 |

## 环境（一次搭建）

```bash
py -3.12 -m venv .venv_bili
.venv_bili/Scripts/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple faster-whisper==1.2.1 av==16.1.0 rapidocr-onnxruntime pillow
```

踩坑定论（照抄，别改）：
- **必须锁 `av==16.1.0`**：av 19 移除了 `metadata_errors` 参数，faster-whisper 1.2.1 调用即崩（TypeError）。
- **模型下载走镜像**：环境变量 `HF_ENDPOINT=https://hf-mirror.com`、`HF_HUB_DISABLE_XET=1` 必须设；不设 Xet 会直连 cas-server.xethub.hf.co 返回 401。
- **用 Python 3.12**，3.14 部分 wheel（ctranslate2 系）有风险。
- Windows 控制台中文乱码是显示问题：所有脚本已内置 `sys.stdout.reconfigure(encoding="utf-8")`，必要时重定向到文件再读。

## 任务A：解析视频（元数据+章节）

```bash
.venv_bili/Scripts/python scripts/bili_meta.py <bvid或URL或b23.tv短链>
```

输出 JSON：标题/UP主(mid)/发布时间/时长/简介/cid/aid/章节(view_points)。后续任务都需要 mid 和 cid。

## 任务B：逐字稿提取（核心链路）

**第0步 先试官方路线（最准，但需登录）**：B 站 AI 字幕与 AI 视频总结接口匿名一律拒绝（`need_login_subtitle:true`、conclusion/get 返回 -101/-403）。若用户愿意在内置浏览器扫码登录 B 站，优先走浏览器带 Cookie 拉 `ai-zh` 字幕 JSON——那是逐字对齐的官方字幕，远胜本地转写。用户不登录才走下面的本地转写路线。

```bash
# 1. 下载音频（和 OCR 校准用的 480p 视频）
.venv_bili/Scripts/python scripts/bili_media.py <bvid> --video
# 2. 转写（small 快；用户嫌不准就用 medium，约慢4倍但错误显著减少）
.venv_bili/Scripts/python scripts/transcribe.py <音频.m4s> --model small --prompt "专有名词热词，逗号分隔"
# 3. OCR 屏幕字幕校准（新闻播报/教程类视频几乎都有内嵌字幕 = UP主的"官方字幕"）
.venv_bili/Scripts/python scripts/ocr_frames.py <视频.m4s> --step 3
```

**转写要点**：
- `--prompt` 塞专有名词热词（从标题、视频简介、首轮转写结果里收集），对品牌名/人名同音错误抑制明显。
- VAD 会跳静音导致**漏句**：small 漏过一句，medium 补上了。交付前用 OCR 时间轴对齐检查空档（如 03:53-03:57 无字幕但屏幕有字）。
- **OCR 校准是准确度跃升的关键**：以屏幕内嵌字幕为基准改 ASR 稿，专有名词/数字/否定词三类错误基本清零。存疑处保留原文标注，别硬改。

**交付格式**：带 [mm:ss] 时间戳的逐字稿 + 修订说明（哪些存疑点、依据是什么）；声明"本地转写+OCR校准稿，非官方字幕"。

## 任务C：UP主全部视频链接

**先读 `references/up-all-videos.md`**——核心结论：B 站空间投稿 API 匿名全被风控（412/-352，wbi 签名+浏览器 Cookie 也救不了），可行路径是"合集接口打底 + 内置浏览器分页器翻页 + view 接口补全"，翻页必须以"列表内容变化"为准而非分页器 active 状态。

## API 风控速查（匿名状态下）

| 接口 | 状态 |
|---|---|
| view / playurl(fnval=16) / player/v2(元数据、章节) | ✅ 匿名可用，带 UA+Referer |
| seasons_archives_list（合集） | ✅ 匿名可用，可翻页 |
| AI字幕 / AI视频总结 / 空间投稿搜索 / 动态流 | ❌ 需登录或被风控 |
| 需 wbi 签名的接口 | Python 实现见 `scripts/bili_meta.py` 内 wbi 函数（MAGIC 表照抄） |

下载流必须带 `Referer: https://www.bilibili.com/` 和 `Range: bytes=0-`，否则镜像可能拒绝。
