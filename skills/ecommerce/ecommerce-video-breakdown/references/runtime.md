# 独立运行与换电脑

本Skill包含解析、身份核对、归档和Excel生成代码。取材由随包Python模块完成。不需要复制原项目、安装它的Node依赖、启动数据库或Web应用。

## 首次使用

需要Python 3.9或更新版本。Windows通常使用“py -3”，macOS和Linux通常使用“python3”。先进入解压后的ecommerce-video-breakdown文件夹，再运行对应命令。

Windows PowerShell：

    py -3 scripts/video_breakdown.py doctor --workspace "E:/视频分析"
    py -3 scripts/video_breakdown.py setup --workspace "E:/视频分析" --with-transcription

macOS或Linux：

    python3 scripts/video_breakdown.py doctor --workspace "./workspace"
    python3 scripts/video_breakdown.py setup --workspace "./workspace" --with-transcription

setup只在指定工作区准备私有依赖，不修改系统全局环境。首次下载依赖和本地模型需要联网。只需字幕和画面时可以省略“--with-transcription”，已有本地稿件的导入和Excel生成无需下载模型。

doctor分别报告归档、图文报告、Excel、内置匿名解析、抽帧和本地转录是否可用。没有模型不代表整个Skill不能运行，不能将“未配置转录”误报为“平台要求登录”。

本地faster-whisper依赖使用随包版本约束（含兼容的PyAV范围），避免音频解码接口不兼容。初始化后再运行doctor，根据实际报告处理缺少的工具。setup失败会保留具体日志及已完成配置，不能把部分安装当成功。

## 配置与工具

本机配置默认保存为工作区runtime.local.json。doctor、setup和ingest可用“--config 文件路径”指定其它配置。相对路径以配置文件所在文件夹为基准；配置示例见随包assets/runtime.example.json。

解析需要的FFmpeg、FFprobe、yt-dlp以及可选本地Whisper由本机发现或私有初始化准备。不能把另一台电脑的绝对路径直接当作本机配置。不得从原自媒体项目或浏览器账号目录补找配置。

Excel优先使用当前Codex可用的表格工具。缺少它或Node时，使用随包的标准库XLSX写入器，仍可新增、追加并保留人工数据。预览使用实际支持的PNG或HTML格式，查看导出结果中的路径，不得声称没有生成的图片已通过验收。

## 日常与迁移

运行ingest、import、prepare、validate、render时指定同一个工作区。新增链接完成分析后，继续更新原来的Excel；不要每批新建文件。

换电脑时，复制Skill即可获得工具；若还要延续原有分析和备注，再复制整个工作区，包括index.json、creators、analyses、reports和Excel导出记录。重新初始化新电脑的运行配置，不复制旧电脑的虚拟环境或浏览器资料。工作区内的Excel位置按相对路径恢复；原先自选的外部Excel不存在时，应明确指定新的输出位置。

只复制Excel不能恢复原视频、证据和分析来源。只有链接、没有原材料的失败记录，也不能因换电脑就变成已分析。

## 独立安装与打包

安装到另一个项目：

    python3 scripts/video_breakdown.py install --target "<项目>/.agents/skills/ecommerce-video-breakdown"

Windows将python3换成py -3。目标是完整Skill文件夹，不是某一个脚本。源码安装与分发包包含SKILL.md、三份许可及权利说明，以及scripts、references、assets和agents中的必要文件。

创建分发包：

    python3 scripts/video_breakdown.py pack --output "./ecommerce-video-breakdown.zip"

ZIP包含文件SHA256清单，不包含运行配置、Cookie、登录资料、视频、报表、模型、虚拟环境或node_modules。不得用外部符号链接代替随包代码。

## 匿名访问的边界

独立化解决本机依赖，不改变平台是否提供公开数据。短链展开后保留实际返回的分享参数，核对笔记或视频身份；不读取登录态，不伪造访问参数，不把登录页当笔记。平台限制匿名访问时停止在线获取，记录原因，改用用户已有的合法本地文件。

取材顺序与数据接入说明见 [media-acquisition.md](media-acquisition.md)。跨系统分支测试不能代替Windows或Linux实机执行记录，验收必须如实区分。
