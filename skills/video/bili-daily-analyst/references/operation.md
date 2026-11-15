# 迁移与运行指南

## 安装与初始化

将整个 `bili-daily-analyst` 文件夹复制到新设备的 `~/.codex/skills/`，重新打开或刷新 Codex。技能自身不含订阅名单、分析报告或历史状态。运行 `python <skill>/scripts/bootstrap.py <工作区>` 创建空工作区；用户决定并提供要分析的博主及周期后，将信息填入 `watchlist.json`。如果希望延续已有订阅和历史进度，单独迁移用户选定的工作区；不复制账号凭据或虚拟环境。自动化需在新设备另行创建。

建议 Windows 或其他能运行 Python 和 Codex 的系统、Python 3.12、网络与足够磁盘。Windows 示例（其他平台使用 venv 对应路径）：

```powershell
py -3.12 -m venv <工作区>/.venv_bili
<工作区>/.venv_bili/Scripts/python -m pip install faster-whisper==1.2.1 av==16.1.0 rapidocr-onnxruntime pillow
```

模型首次运行须联网下载，可能耗时和占用大量空间。脚本默认 `HF_ENDPOINT=https://hf-mirror.com`、`HF_HUB_DISABLE_XET=1`；不可用时选择当前环境可访问的可信下载源。OCR 不可用时说明。长视频与多 P 处理可能耗时，不得悄悄截断。字幕可能需要用户在受支持的浏览器登录；不保存或输出 cookie、密码。

## 采集

工具位于 `<skill>/assets/toolkit/scripts`。`bili_search_ups.py` 可导入 `get_buvid()`、`wbi_keys()`、`search_type()` 做候选搜索；结果无法证明完整覆盖。可参考 `<skill>/assets/toolkit/references/up-all-videos.md` 的空间页翻页、合集与 view 接口思路，文中的旧浏览器插件名称和静态 API 可用性是历史经验，按当前宿主工具和实际响应调整。列表页按实际顺序翻到早于窗口起点或确认末页，只有连续且可验证覆盖时才记为已覆盖；合集不能证明空间全部投稿。遇风控、缺页或未渲染，记录受限和已尝试来源，不将空结果当作无更新。`bili_meta.py <BV>` 可取 MID、CID、发布时间等，核对多 P 信息。站点策略可能变化，遇变化调整并记录证据。

## 媒体与转写

`<py>` 是工作区虚拟环境的 Python，`<tools>` 为上述工具目录：

```text
<py> <tools>/bili_meta.py BV号
<py> <tools>/bili_media.py BV号 --cid CID --out 某BV某P专用目录
<py> <tools>/transcribe.py 音频文件 --model small --out 逐字稿文件
<py> <tools>/bili_media.py BV号 --cid CID --video --out 某BV某P专用目录
<py> <tools>/ocr_frames.py 视频文件 --step 3
```

先创建输出目录。`bili_media.py` 会按 BV 命名，故每 P 必须使用独立目录；每 P 记录 CID、原始时长、状态和结果路径。先尝试现有官方字幕；机器识别不能称官方稿。VAD 可能漏句，检查空白段，可关闭 VAD 重试或听辨；OCR 是辅助，不把高幻觉概率内容当事实。有访问限制时如实记录，不绕过权限限制。

## 状态和自动化

周期任务每个窗口至少记录起止时间、计划日、账号身份/覆盖/错误、每个 BV 的 MID、分 P 状态、转写来源、缺失段、路径、失败原因及重试状态；只有确认处理完整才标完成。重试时按 BV 和 CID 复用已成功部分，中断也要落盘。

用户要求设置每日任务时，通过当前自动化管理工具设定时间和时区，绑定工作区和本技能。提示词示例：

> 使用 $bili-daily-analyst 分析工作区【本机持久目录】中我指定的订阅账号，按本次计划时间统计窗口，补查遗漏及重试失败，保存日报与状态并报告覆盖和遗漏风险。

在界面核实下一次运行时间、项目/会话、机器在线与通知设置。迁移后若旧设备仍运行同一任务，应由用户决定启用哪一份，不静默修改。
