# 第三方工具与内容说明

本Skill最初从用户指定的 ecommerce/video-breakdown 项目归集，当前版本的媒体取材部分于2026-10-27在本仓库重新实现。当前文件和来源版本的SHA-256、仓库新增文件见根目录catalog.json；不把初次收录记录当作当前文件逐字节未修改的声明。LICENSE仅覆盖不吃辣的Chris有权授权的内容。

- scripts/public_media.py 包含三平台匿名分享页、身份验证、媒体工具调度和本地缓存流程；scripts/subtitle_formats.py 随包包含本仓库通用字幕格式读取代码，不依赖其它Skill。B站WBI签名使用平台协议规定的参数和置换表。
- 实际使用的Python、FFmpeg、FFprobe、yt-dlp、static-ffmpeg、Whisper、faster-whisper、PyAV及模型和传递依赖适用各自许可；随包不包含已安装环境或模型。依赖清单见assets/requirements.txt与assets/requirements-transcription.txt。
- Excel可使用宿主表格工具或随包标准库写入器；可选Node导出路径的外部库适用各自许可，未随包复制其依赖目录。
- 待分析的视频、图片、字幕和博主内容按各自来源和授权使用。分析方法的公开依据保留在references/research.md；改写程序名称不改变外部内容或工具的权利归属。
- 不归集真实媒体、博主数据、业务Excel、账号、Cookie、凭据、模型或运行工作区；复制完整Skill仍需在新电脑按需初始化工具。
