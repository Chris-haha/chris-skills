---
name: video-text-redactor
description: Use when a user supplies a video and wants selected on-screen text or regions hidden, including 博主名称打码、账号脱敏、文字马赛克、遮邮箱手机号 and screen recordings with zoom, pan, scrolling or cuts. Supports arbitrary specified words and semantic target categories. Not for removing subtitles to recover the original picture.
---

# 视频文字跟踪打码

把用户给的视频和自然语言遮挡要求转换为可复查的规则，在本机输出打码成片。核心是**语义选目标，逐帧定位，运动补漏，成片复扫**。不能用几个抽帧上的固定框冒充全片跟踪。

## 启动

脚本均相对此 skill 目录；先确定实际目录，再使用绝对路径。下文 `$REDACTOR` 表示 `scripts/bootstrap.sh` 的绝对路径，不依赖工作目录。

```bash
"$REDACTOR" doctor
"$REDACTOR" scan "/path/input.mp4" --out "/path/job/scan"
```

首次运行自动创建独立 Python 环境并安装 `scripts/requirements.txt`，编译 Swift OCR。需要 macOS、Swift 命令行工具、FFmpeg/ffprobe；依次查环境变量 `FFMPEG` / `FFPROBE`、PATH、`~/.local/text-video-tools`、Homebrew。依赖缺失时给出实际错误，勿假装已处理。Linux/Windows 暂无此 OCR 后端。

## 理解目标并生成规则

- 用户指定词语：直接使用；支持多词、正则、邮箱/手机号等预设、全部文字，以及非文字区域。
- 用户只给视频且说“打码”，沿用会话内目标；本 skill 的工作台场景默认隐藏第三方博主昵称、署名、账号、身份链接。用户已指定范围时以其要求为准。目标无法从上下文判断时只问一条范围问题，同时先扫描。
- 用户说“博主名/客户名/公司名”等语义类别：读取 `scan/candidates.json`、`ocr.jsonl` 和联系表，实际查看相关画面，利用列表、头像、署名栏等上下文选出具体词语。**脚本只识字和执行规则，语义分类由当前 Codex 完成**，不依赖外部模型或固定的人名词典。不要让用户手抄姓名和坐标。
- 在同一视频内搜索目标的其他出现方式：标题标签、详情页、浏览器标题、弹窗、侧栏、大小写/全角形式和 OCR 别字。将确认过的别名加入规则；未要求的标题、数据和界面文字保留。
- 抽帧扫描仅用于发现，可能漏掉一帧的新身份。render 会记录每帧 OCR，并生成 `candidates-full.json`。按语义类别处理时，必须再次检查这份完整候选集和必要的原始帧；发现新目标则补规则重新导出，不能只复查初始名单。

规则保存到该视频独立的 `job/rules.json`，不要写进全局 skill。字段和区域坐标见 [references/rules.md](references/rules.md)。例如：

```json
{
  "version": 1,
  "intent": "隐藏指定姓名与邮箱，保留其他标题和数据",
  "terms": ["测试博主甲"],
  "presets": ["email"],
  "padding": 10,
  "mode": "mosaic"
}
```

## 处理缩放、移动和切镜头

```bash
"$REDACTOR" render "/path/input.mp4" \
  --rules "/path/job/rules.json" --output "/path/delivery/input-打码.mp4"
```

默认原分辨率逐帧 OCR，不跳帧；Vision 字符框精确遮住匹配子串，缺少可靠字符框时覆盖整行，不用等宽猜测。逐帧稀疏光流估计平移、缩放和轻微旋转；前后向检查与 RANSAC 剔除不可靠运动。双向补足短时 OCR 漏检，镜头变化重置；大幅模糊/长时失踪可能仍需追加区域或时间规则。

相同原视频修正规则后，可加 `--ocr-cache /path/previous.redaction` 复用逐帧 OCR；脚本校验输入 SHA-256、尺寸、帧率与帧序列。新增目标若先前被 OCR 误读，仍需新一轮 OCR，不能指望缓存补识别。缓存缺少新增词的字符框时会保守遮整行。

`--ocr-width 2560` 可加速 4K 视频，但必须明确记录降采样，并用原分辨率复扫。不能为加速静默降低检测频率。`--bridge-seconds` 和 `--track-seconds` 默认均为 0.3 秒，限制目标消失后旧框的残留；重新识别到文字时还会沿可靠运动向前追溯最多 1 秒补漏。已确认持续存在的目标可延长 track-seconds，但会增加目标消失后的多余遮挡，长缺口写报告。失去可靠跟踪的显式区域会整帧遮挡至该区域结束，并标记复核。

默认强马赛克，每个目标最多 4×2 色块；用户要更彻底隐藏可用 `mode: solid`。不使用容易辨认笔画的弱模糊。保留原声、画面尺寸及恒定帧率；VFR 会先按原时间轴转 CFR 并写入报告。音视频起点相差超过 50ms 时脚本拒绝处理，应先用 FFmpeg 明确对齐，不能私自丢掉偏移。

## 检查与交付

```bash
"$REDACTOR" verify "/path/delivery/input-打码.mp4" \
  --rules "/path/job/rules.json" --out "/path/job/verify"
```

1. 检查 `.redaction/report.json` 中帧数、尺寸、原声、时长偏差、`unmatched_terms` 和跟踪 warnings。别名未命中可结合原图解释；实际目标未命中不能当作成功。
2. 复核完整候选集，查看打码成片及 `.redaction/compare-*.jpg`，重点看首次/最后出现、放大缩小、移动、滚动、切镜头和报告标记帧。需要时用 OpenCV 抽取指定帧，不依赖联系表覆盖全部细节。
3. verify 对**最终编码文件的每帧**复扫；发现已知目标命中时返回 2，输出泄漏帧和坐标。先修规则/区域并重导，再复扫。`no_known_target_ocr_hits` 仅表示没有识别出规则内文字；同一 OCR 引擎复扫不能证明所有未识别身份均已消失。
4. 输出打码视频、规则和精简检查结论。存在未解决跟踪缺口/未确认目标时明确标为待复核版本，不称“零泄露”或“可放心发布”。不提供未经评估的法律保证。

原视频不覆盖。每次结果和诊断放在单独目录。`.redaction` 内的 OCR、规则、原图对比仍含原始敏感文字；保留在本机供复核，**不要默认上传、分享或嵌入对外报告**。向用户展示打码版图片/视频即可。无需额外生成封面。
