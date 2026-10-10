---
name: voice-driven-video
description: "Use when a user provides a narration script and their own voice recording to produce a faceless motion graphics video, wants subtitles and scenes to follow a new recording automatically, or needs a reusable manuscript-to-video workflow. 口播稿、本人录音、不露脸视频、录音与画面不同步、自动重排字幕和分镜。"
---

# 录音驱动动态图解

把口播稿与真实录音制作成可编辑、不露脸的视频。Codex负责分镜和视觉判断，脚本负责音频准备、时间线、渲染和媒体检查。以当前音轨为唯一时钟；目标时长用于写稿阶段估算，不能靠裁掉录音或加速本人声音强行满足。

## 输入与执行

1. 找到口播稿、录音、参考视频或品牌约束。已有授权和偏好直接沿用。用户只给稿件时先完成分镜和静帧；缺少本人录音时明确说明尚不能按本人节奏定版，可做标为临时配音的预览，不冒充本人声音。
2. 按 [recording.md](references/recording.md) 指导自然录音，先整理最终要保留的口播，再对齐。保留原文件，处理产生新文件；已有原声含音乐时记录这个事实。
3. 创建新项目：`python3 SKILL_DIR/scripts/init_project.py --output PROJECT_DIR`。用可用Node运行 `npm ci`。先检查本机ffmpeg、ffprobe、whisper-cli及模型；只安装确实缺的依赖。按 [timing.md](references/timing.md) 创建项目venv并安装scripts/requirements.txt；以下Python命令使用该解释器，渲染前设置VIDEO_PYTHON为其绝对路径。
4. 写项目 `script.json`：`{title,fps,units:[{id,text}],scenes:[{id,anchorUnit,label}]}`。unit按一句或一个自然呼吸段划分，使用稳定ID；scene引用unit的ID。内容以实际录音为准，数字、专有词、跳读、重录要复核，不能硬把另一版稿套上去。
5. 准备音轨：`python3 SKILL_DIR/scripts/prepare_audio.py --input RECORDING --output-dir PROJECT_DIR/out/audio`。这会生成48k规范副本、16k识别副本、波形和来源摘要，保留实际时长。
6. 用实际ASR得到时间信息：`python3 SKILL_DIR/scripts/run_asr.py --audio PROJECT_DIR/out/audio/canonical.wav --model MODEL --output-prefix PROJECT_DIR/out/audio/asr --timing-policy segment`。它记录实际识别命令与音轨摘要，后续严格验证关联。整句字幕和镜头优先句段时间；逐字效果可选token，但要复核累计提前或漂移。DTW若失败切换句段或token offsets并标为近似。完整JSON有时包含拆开的中文UTF-8 token字节，配套解析器处理此情况。
7. 对齐：`python3 SKILL_DIR/scripts/align_narration.py --audio PROJECT_DIR/out/audio/canonical.wav --asr PROJECT_DIR/out/audio/asr.json --asr-manifest PROJECT_DIR/out/audio/asr.manifest.json --timing-policy segment --script PROJECT_DIR/script.json --output PROJECT_DIR/src/timeline.json`。阅读coverage、needsReview和report；检查新增长停顿是否被ASR错算到下一句，使用当前PCM静音边界修正，含背景音乐或底噪时重点复核；明显错稿应停止并修正文稿，低置信内容只复核相关段。脚本的句段/token时间匹配是近似对齐，不是声学强制对齐。真正需要逐字卡点时按 [timing.md](references/timing.md) 升级对齐或复核关键事件。
8. 按 [visual-direction.md](references/visual-direction.md) 完成实际内容的分镜与素材。修改 `src/storyboard.json` 和 `src/Film.tsx`；通用起点只解决结构，不能把自动卡片预览作为设计完成。先检查三个代表静帧，之后再全片渲染。镜头边界、字幕、波形和重点动作从timeline读取，禁止散落固定绝对秒数。
9. 拷贝规范音轨到`public/audio/voice.wav`，在项目中执行 `node render.mjs stills` 和 `node render.mjs render`。入口会核对音轨摘要，拒绝过期时间线。渲染静音MP4，再执行 `python3 SKILL_DIR/scripts/mux_audio.py --video PROJECT_DIR/out/silent.mp4 --voice PROJECT_DIR/public/audio/voice.wav --timeline PROJECT_DIR/src/timeline.json --output PROJECT_DIR/out/final.mp4`。这里不套用其他项目的AAC延迟常数。
10. `python3 SKILL_DIR/scripts/verify_media.py --video PROJECT_DIR/out/final.mp4 --voice PROJECT_DIR/public/audio/voice.wav --output-dir PROJECT_DIR/out/qa`。另看字幕边界、关键帧、转场逐帧与正常速度播放；有独立审阅能力时交给隔离上下文做终检。没有听过音轨就不声称主观听感通过。

交付MP4、SRT、可编辑工程、来源与QA报告。清楚标注临时配音或参考原声。完整保留用户声音并通过解码同步测量后，才能说播放与录音的时间一致；不能把编码同步误差当作文本内容对齐精度。

## 换录音

重新运行准备、转写、对齐、静帧、渲染、合音和检查。字幕和场景跟新录音重排，新增停顿会留出自然hold；整体更长时保留完整录音并更新视频总长。长时间静音、错误重录、文字差异先在音频编辑阶段处理；不要让动画替录音质量兜底。

## 脚本与数据契约

所有命令使用实际绝对路径替换大写占位符，不把用户文字拼进shell。详细字段和复核方法见 [timing.md](references/timing.md)。`reviewedUnits`只允许基于波形/音频复核的起止时间，必须写reason；不得用均匀分配时间制造精准字幕。更换音轨后这些人工时间失效，应重新复核。

脚本依赖Python3、numpy、opencc-python-reimplemented、ffmpeg/ffprobe；Remotion起点固定已验证版本，更新需重新检查。私有录音默认本地转写；需要外部服务时先沿用用户明确授权的服务。录音不够、对齐不可靠、素材不存在时如实报告并完成能独立推进的部分。
