---
name: media-urls-batch-archive
description: 当用户提供一个或多个视频链接，或指定任意目录中的链接文件，要求批量提取字幕、转录并按博主和视频归档时使用。支持直接链接与一行一条的集中读取，随包自带解析和归档代码，可迁移到新电脑。
---

# 视频链接批量归档

读取用户提供的链接，按 `<输出目录>/<博主名>/<视频名>/` 保存文字稿和元数据。代码全部在本目录内，不需要其他 skill、原项目或 npm。Python 和运行软件在新电脑初始化，不能直接搬用旧电脑的虚拟环境。

## 接收输入

用户未提供来源时，提示：

> 可以直接把一个或多个视频链接发给我；也可以在任意目录新建 UTF-8 文本文件，一行放一条视频链接，再告诉我文件路径或所在目录。也可以一起说明结果保存在哪里。

- 已提供的信息直接使用，不重复追问。支持直接链接，或任意位置的文件。推荐 `.txt`、`.md`，兼容 UTF-8 BOM、分享文案和重复链接。
- 只有目录时，只检查本层 `.txt`、`.md`：唯一文件直接读取；多个文件列出名称让用户选择；没有文件时提示补充。不得猜测来源或递归扫描整个磁盘。
- 用户未指定输出时，文件输入使用链接文件同级的 `视频归档/`；直接链接使用当前工作目录的 `视频归档/`。告知实际路径，并显式传入脚本。

## 首次使用与迁移

定位本 SKILL.md 所在目录，使用该目录内的脚本绝对路径，不假定当前工作目录。首次使用、新电脑或依赖报错时，读取 [迁移与安装说明](references/migration.md)。

需要 Python 3.11+，推荐 3.12。用选定的 Python 执行：

```bash
python3 "/实际skill目录/scripts/runtime.py" setup
python3 "/实际skill目录/scripts/runtime.py" doctor
```

`setup` 创建本机专用虚拟环境，安装下载、字幕和本地语音识别依赖；缺少 FFmpeg/FFprobe 时自动取得适配当前系统的版本，并准备本地 Whisper base 模型。需要联网和磁盘空间。`doctor` 检查实际解释器、工具和模型；未通过时先处理它列出的缺项。

安装产物默认位于用户主目录的 `.cache/media-urls-batch-archive/`，不写入技能源码。可用 `MEDIA_URLS_RUNTIME` 指定另一目录，后续命令保持相同设置。仅需字幕时可选 `setup --subtitles-only`；需要无字幕视频转录时重新执行完整 `setup`。

## 批量执行

使用 [运行入口](scripts/run.py)，自动选择初始化好的本机 Python 环境。示例路径和 URL 替换为本次实际值：

```bash
python3 "/实际skill目录/scripts/run.py" \
  --url "https://example.com/video/1" \
  --url "https://example.com/video/2" \
  --output-dir "/本次输出目录/视频归档"
```

文件或唯一候选目录输入时，将 `--url` 参数替换为 `--input "/实际链接文件或目录"`。`--url` 可重复，不能和 `--input` 混用。始终传 `--output-dir`，输入文件保留原样。

本 Skill 的输入处理、字幕格式解析、转录调度、缓存、归档和迁移流程为自主定制实现，代码见 [media_pipeline.py](scripts/media_pipeline.py)。平台接入调用 yt-dlp 的公开命令接口；优先取字幕，YouTube 可补充使用字幕接口，无字幕时本地语音转录。

支持范围取决于 yt-dlp 对 B站、YouTube、抖音、小红书、TikTok 等网站的适配，以及平台访问条件和网络。保留用户给出的分享与分P参数，不猜测另一条视频或其他分P来替代。失败保留真实原因，不把页面描述、摘要或空文字稿作为逐字稿。

默认不抽帧；确有需要可在本机配置中启用。语言、模型、工具路径等见 [配置示例](config.example.json)，使用 `--config "/本机配置.json"` 选择配置；相对文件路径相对于配置文件。用户明确提供登录 Cookie 文件时才配置 `cookies_file`，不自动读取浏览器或复制旧机器凭据。

## 结果与续跑

每条成功结果包含 `metadata.json`、`transcript.txt`、`transcript-cleaned.txt`、`source-url.txt`、`README.md`。清理稿只合并空白，不改写原意。根目录保存 `summary.json`、`failures.json`、`run.log`。

同一输出目录默认跳过完整归档，失败条目下次继续处理；不同链接同名时增加编号。只有用户要求重新处理已完成链接时才加 `--no-skip-existing`。`--retries` 控制额外重试次数，默认 1；失败不会中断后续链接。退出码 0 表示全部成功或跳过，1 表示存在失败，2 表示输入或配置有误。

结束时报告输入数量、成功/跳过/失败数量、实际保存位置及失败原因。不能把只有元数据或空文字稿的结果视为成功。

## 搬到另一台电脑

复制整个 `media-urls-batch-archive/` 目录，或使用已生成的迁移 ZIP；解压后执行该电脑上的 `setup`、`doctor`。不需要本项目的其他目录。完整步骤、Windows 命令和离线自检见 [迁移说明](references/migration.md)。自主开发范围和开源工具依赖见 [开发与依赖说明](THIRD_PARTY_NOTICES.md)。
