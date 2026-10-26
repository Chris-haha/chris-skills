# 独立迁移与安装

## 要复制什么

复制整个 `media-urls-batch-archive/` 目录，包含 SKILL.md、scripts（含本技能的 media_pipeline.py）、requirements 文件、配置示例、references、tests 和来源说明。也可以解压迁移 ZIP。不要只复制 SKILL.md。

不需要原项目、Node/npm、其他 skill 或原电脑的用户目录。运行文件可放任意位置；如果要由 Agent 自动发现，放进目标 Agent 的技能目录，并按该 Agent 的加载方式启用。直接运行脚本不依赖某款 Agent。

## 新电脑第一次运行

准备 Python 3.11 或更新版本（推荐 3.12，带 pip 和 venv）。Ubuntu/Debian 若缺 venv，需要相应 Python 的 venv 软件包。使用实际安装的合适版本，示例中 `/path/to/...` 是需要替换的路径。

macOS / Linux：

```bash
python3 "/path/to/media-urls-batch-archive/scripts/runtime.py" setup
python3 "/path/to/media-urls-batch-archive/scripts/runtime.py" doctor
python3 "/path/to/media-urls-batch-archive/scripts/run.py" \
  --input "/path/to/视频链接.txt" --output-dir "/path/to/视频归档"
```

Windows PowerShell（已安装 Python 3.12 和 Python Launcher）：

```powershell
py -3.12 "D:\skills\media-urls-batch-archive\scripts\runtime.py" setup
py -3.12 "D:\skills\media-urls-batch-archive\scripts\runtime.py" doctor
py -3.12 "D:\skills\media-urls-batch-archive\scripts\run.py" --url "https://example.com/video/1" --output-dir "D:\视频归档"
```

`setup` 会下载 Python 依赖、按需取得 FFmpeg/FFprobe，以及准备本地 Whisper base 模型。下载总量取决于平台和已安装工具，需联网并预留约 2 GB 空间。默认使用 CPU，无需 GPU、API Key 或付费转录服务。模型可能需要几分钟下载；网络失败时保留错误，网络恢复后重跑即可。

只处理有字幕的视频时可用 `setup --subtitles-only`，省去语音识别包与模型；它不能完成无字幕视频的转录。以后需要转录时重新运行完整 `setup`。

工具安装在用户目录 `.cache/media-urls-batch-archive/`，包含 venv、config.json、models、parser-state。脚本不要求激活 venv，`run.py` 和 `doctor` 自动选择它。

定制存储位置时，在上述所有命令前保持相同环境变量设置：

```bash
export MEDIA_URLS_RUNTIME="/another/location/media-archive-runtime"
```

PowerShell 对应 `$env:MEDIA_URLS_RUNTIME = "D:\media-archive-runtime"`。

## 配置与平台限制

示例见 [config.example.json](../config.example.json)。初始化会生成本机 config.json；可直接编辑，或通过 `--config` 指定另一个 JSON 文件。相对工具、Cookie、模型文件路径都相对于该配置文件。

- `language`：默认 `zh`；其他语言可设 `en`，自动识别设 `auto`。
- `whisper_model`：已准备的 faster-whisper 模型目录，或首次下载用的模型名，如 `base`。手动指定模型目录时，需要包括 `model.bin` 和其配套配置、词表等文件。
- `ffmpeg` / `ffprobe`：默认自动发现；初始化取得的工具使用本机实际路径。
- `extract_frames`：默认 false。启用时关键帧复制到单条归档的 `frames/`，metadata 引用归档内相对路径。
- `cookies_file`：仅用户显式提供时填写 Netscape Cookie 文件路径，不自动发现浏览器。公开访问失败、登录限制或视频下架会成为失败记录；不能保证所有链接成功。
- `--extractor-path` / `MEDIA_URLS_EXTRACTOR_PATH`：仅兼容自定义解析器，正常迁移不需要。应清除旧机器残留的外部解析器覆盖设置。

B站保留用户的分P参数，交给下载器选择对应内容；平台描述和摘要不作为逐字稿。输入始终要求 http/https 链接；无需把链接文件放在技能目录。

## 迁移时不带什么

不复制旧电脑的 venv、原机工具二进制、账号凭据和真实视频归档。跨系统需要重新执行 setup，旧绝对路径不会自动适配。若配置了 `MEDIA_URLS_RUNTIME` 或 `MEDIA_URLS_CONFIG`，新电脑也需要对应设置或清除覆盖值。

本包是可迁移的代码包，不包含所有平台的软件安装包和模型；全新电脑首次使用需要下载。完全离线的新电脑仍需预先准备目标系统的依赖轮子、FFmpeg/FFprobe 和模型，迁移 ZIP 本身不承诺离线安装。

## 不联网的功能自检

不需要 pytest，也不会访问真实视频网站：

```bash
python3 -m unittest discover -s "/path/to/media-urls-batch-archive/tests" -v
```

测试使用隔离 HOME、空的其他技能目录、中文及空格路径与可控下载器/转录器，验证包内解析调用、归档、续跑、错误报告和输入保护。该测试不能证明某个平台当前可访问，也不能代替真实模型识别质量评估。

## 排障

先运行 doctor，查看 ready 和各项检查。若下载中断、Python 不匹配或缺依赖，用正确解释器重跑 setup。需升级下载器时也可重跑 setup（依赖清单满足时 pip 可能保留原版本）；平台解析失效时可在本机 venv 中升级 yt-dlp。

批次中个别链接失败不会中断后续链接。查看输出根目录 failures.json 和 run.log；修复原因后复用同一链接文件和输出目录，已完成条目会跳过。强制重跑已完成链接使用 `--no-skip-existing`，它绕过解析缓存。
