# 开发范围与工具依赖

本 Skill 的用户输入引导、链接整理、字幕格式读取、转录调度、缓存、关键帧整理、目录归档、失败续跑、环境初始化和迁移包装为自主定制实现。代码在 scripts/ 中，不需要其他 skill 或原项目。

平台接入通过 yt-dlp 的公开命令接口完成；本地语音识别调用 faster-whisper。可准确表述为“自主定制开发的视频批量归档 Skill，使用通用开源工具完成平台接入和本地转录”。这些基础工具及模型本身不属于本 Skill 的原创范围。

## 运行依赖

- Python：运行脚本和隔离环境。
- yt-dlp：平台视频信息、字幕与媒体下载。
- youtube-transcript-api：YouTube 字幕补充通道。
- FFmpeg / FFprobe：媒体处理和关键帧提取。
- static-ffmpeg：按目标系统取得媒体工具。
- faster-whisper、PyAV、CTranslate2 及 Whisper 模型：本地语音识别。

这些工具及其传递依赖适用各自许可；初始化时安装，迁移包不复制其已安装代码或模型。版本范围见 requirements.txt 和 requirements-transcription.txt。

技能目录不包含账号凭据、Cookie、浏览器数据、个人运行环境、模型或真实视频归档。安装依赖与模型的本机目录在首次 setup 时创建。
