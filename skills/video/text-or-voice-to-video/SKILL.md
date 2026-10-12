---
name: text-or-voice-to-video
description: "Create editable faceless motion graphics videos from a text manuscript with Doubao AI narration, or from an existing voice recording. Use for 文字生成视频、文字稿配音、口播稿、本人录音、不露脸视频、自动对齐字幕与分镜, or replacing narration while retaining editable visuals."
---

# 文字／录音转动态图解视频

把文字稿或已有录音制作成可编辑、不露脸的动态图解视频。仅有文字稿时用豆包语音合成生成正式 AI 旁白，再按实际音轨对齐字幕和画面。Codex负责分镜和视觉判断，脚本负责配音、音频准备、时间线、渲染和媒体检查。以当前音轨为唯一时钟；目标时长用于写稿阶段估算，不能靠裁掉录音或加速本人声音强行满足。

## 选择输入

- 仅文字稿：进入豆包配音模式，读取 [narration.md](references/narration.md)。支持粘贴文字及 UTF-8 TXT/Markdown；保留原稿，清理格式符号，默认不改写或删减正文。用户文字经文件或结构化参数传入，不拼接进shell。
- 已有录音：沿用原流程，无需豆包密钥。两者都提供且未另行说明时优先录音，以实际说出的内容修订字幕稿。
- 已有偏好直接沿用；否则默认中文普通话、原语速、1920×1080、30fps、不露脸动态图解。首版云端配音仅接豆包系统音色，不做声音克隆、数字人口型或整片文生视频。

## 输入与执行

1. 找到稿件、可选录音、参考视频或品牌约束。文字稿模式生成的声音明确标为 AI 合成；已有录音不能自动改成合成声音。
2. 录音模式按 [recording.md](references/recording.md) 指导自然录音，先整理最终要保留的口播，再对齐。保留原文件，处理产生新文件；已有原声含音乐时记录这个事实。
3. 创建新项目：`python3 SKILL_DIR/scripts/init_project.py --output PROJECT_DIR`。用可用Node运行 `npm ci`。先检查本机ffmpeg、ffprobe、whisper-cli及模型；只安装确实缺的依赖。按 [timing.md](references/timing.md) 创建项目venv并安装scripts/requirements.txt；以下Python命令使用该解释器，渲染前设置VIDEO_PYTHON为其绝对路径。
4. 文字模式在初始化工程后运行 `python3 SKILL_DIR/scripts/prepare_script.py --input MANUSCRIPT --output-dir PROJECT_DIR --replace-script`，生成可编辑 `script.json`、原稿副本、朗读稿和 `narration.json`；`--replace-script`会替换草案分镜，后续只改某句时直接编辑script，不必重建已设计分镜。录音模式继续手写 `{title,fps,units:[{id,text}],scenes:[{id,anchorUnit,label}]}`。unit按一句或自然呼吸段划分，scene引用稳定unit ID。数字、专有词和实际说出的内容要复核。
5. 文字模式先运行 `python3 SKILL_DIR/scripts/synthesize_narration.py --script PROJECT_DIR/script.json --config PROJECT_DIR/narration.json --output-dir PROJECT_DIR/out/narration --dry-run` 查看字符数与缓存命中，再去掉`--dry-run`生成配音。密钥仅从`DOUBAO_TTS_API_KEY`读取，缺少密钥时完成能独立推进的分镜与配置，明确阻塞，不冒充已生成配音。用生成的`PROJECT_DIR/out/narration/voice.wav`作为下一步RECORDING；录音模式用原录音。随后运行 `python3 SKILL_DIR/scripts/prepare_audio.py --input RECORDING --output-dir PROJECT_DIR/out/audio`，生成48k规范副本、16k识别副本、波形和来源摘要，保留实际时长。
6. 用实际ASR得到时间信息：`python3 SKILL_DIR/scripts/run_asr.py --audio PROJECT_DIR/out/audio/canonical.wav --model MODEL --output-prefix PROJECT_DIR/out/audio/asr --timing-policy segment`。它记录实际识别命令与音轨摘要，后续严格验证关联。整句字幕和镜头优先句段时间；逐字效果可选token，但要复核累计提前或漂移。DTW若失败切换句段或token offsets并标为近似。完整JSON有时包含拆开的中文UTF-8 token字节，配套解析器处理此情况。
7. 对齐：`python3 SKILL_DIR/scripts/align_narration.py --audio PROJECT_DIR/out/audio/canonical.wav --asr PROJECT_DIR/out/audio/asr.json --asr-manifest PROJECT_DIR/out/audio/asr.manifest.json --timing-policy segment --script PROJECT_DIR/script.json --output PROJECT_DIR/src/timeline.json`。阅读coverage、needsReview和report；检查新增长停顿是否被ASR错算到下一句，使用当前PCM静音边界修正，含背景音乐或底噪时重点复核；明显错稿应停止并修正文稿，低置信内容只复核相关段。脚本的句段/token时间匹配是近似对齐，不是声学强制对齐。真正需要逐字卡点时按 [timing.md](references/timing.md) 升级对齐或复核关键事件。
8. 按 [visual-direction.md](references/visual-direction.md) 完成实际内容的分镜与素材。修改 `src/storyboard.json` 和 `src/Film.tsx`；通用起点只解决结构，不能把自动卡片预览作为设计完成。先检查三个代表静帧，之后再全片渲染。镜头边界、字幕、波形和重点动作从timeline读取，禁止散落固定绝对秒数。
9. 拷贝规范音轨到`public/audio/voice.wav`，在项目中执行 `node render.mjs stills` 和 `node render.mjs render`。入口会核对音轨摘要，拒绝过期时间线。渲染静音MP4，再执行 `python3 SKILL_DIR/scripts/mux_audio.py --video PROJECT_DIR/out/silent.mp4 --voice PROJECT_DIR/public/audio/voice.wav --timeline PROJECT_DIR/src/timeline.json --output PROJECT_DIR/out/final.mp4`。这里不套用其他项目的AAC延迟常数。
10. `python3 SKILL_DIR/scripts/verify_media.py --video PROJECT_DIR/out/final.mp4 --voice PROJECT_DIR/public/audio/voice.wav --output-dir PROJECT_DIR/out/qa`。另看字幕边界、关键帧、转场逐帧与正常速度播放；有独立审阅能力时交给隔离上下文做终检。没有听过音轨就不声称主观听感通过。

交付MP4、独立旁白音频、SRT、可编辑工程、素材来源与QA报告；AI模式另附配音manifest，说明服务、音色和用量，明确标注AI合成，不将它称为临时声音或用户本人声音。清楚标注参考原声。完整保留音轨并通过解码同步测量后，才能说播放与音轨的时间一致；不能把编码同步误差当作文本内容对齐精度。

## 改稿与换声音

文字模式直接修改script.json中的unit文本或narration.json中的音色/语速，再运行配音脚本。同一自然段内的units通过可选paragraphId合成一段，默认最多300字符；只有变化的合成分段会重做，音色或语速改变会使对应缓存失效。成功的分段可断点续跑；认证、额度和音色错误立即停止，临时网络或服务错误最多重试两次。失败后out/narration/voice.wav及成功manifest失效，不能继续用旧配音冒充新结果；已经拷贝到public的旧文件也不能继续渲染本次稿件。重试可能重复产生服务用量，以控制台结算为准。

新配音或新录音都必须重新运行准备、转写、对齐、静帧、渲染、合音和检查，并删除旧reviewedUnits后重新复核。字幕和场景随新音轨重排，新增停顿留出自然hold；整体更长时保留完整音轨并更新视频总长。固定时长需求先调整稿件或AI语速再合成。长时间静音、错误重录、文字差异先在音频编辑阶段处理；不要让动画替录音质量兜底。

## 脚本与数据契约

所有命令使用实际绝对路径替换大写占位符，不把用户文字拼进shell。详细字段和复核方法见 [timing.md](references/timing.md)。`reviewedUnits`只允许基于波形/音频复核的起止时间，必须写reason；不得用均匀分配时间制造精准字幕。更换音轨后这些人工时间失效，应重新复核。

稿件整理与豆包配音只需Python标准库；原对齐流程依赖numpy、opencc-python-reimplemented、ffmpeg/ffprobe及真实Whisper程序和模型。Remotion起点固定已验证版本，更新需重新检查。私有录音默认本地转写；云端配音仅发送待朗读文本，不上传已有录音。凭证缺失、对齐不可靠、素材不存在时如实报告并完成能独立推进的部分。测试用合成信号或模拟服务响应只能作为管线验证，不能交付为豆包真实配音样片。
