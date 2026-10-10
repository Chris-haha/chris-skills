# 时间与验证契约

脚本输入：

```json
{"title":"主题", "fps":30,
 "units":[{"id":"u1","text":"第一句话。"},{"id":"u2","text":"第二句话。"}],
 "scenes":[{"id":"s1","anchorUnit":"u1","label":"介绍"},{"id":"s2","anchorUnit":"u2","label":"解释"}]}
```

输出timeline包含实际durationMs、ceil(duration×fps)的durationFrames、audio摘要、captions、scenes、每帧waveform、alignment与provenance。caption有文本、毫秒区间、置信分数、needsReview和timingSource；scene引用同一字幕ID计算区间。帧区间覆盖完整片长，尾部最多补足不足一帧。字幕在毫秒区间显示，不能用随意取整造成两个字幕同时显示。

默认句段时间用于整句字幕与场景，避免短token累计提前。`--timing-policy token`适用于需要细粒度标记并愿意复核时；`--timing-policy segment`在真实句段内插值并保留近似标记。

ASR输入使用whisper.cpp完整JSON，offsets以毫秒计；t_dtw以10毫秒tick计。token可能包含多个字，内部字时间是估算；缺字仅在相邻证据间插值并标记。confidence是文本匹配率与识别概率组合，不能当成校准过的时间准确率。明显错稿会产出blocked报告而退出，修正输入后重跑。

识别器可能把一段长停顿归入后一整句。脚本会用当前规范音轨做保守的静音起点检查：在长、极低音量区间内的句子起点，只有找到同一估计区间里的实际声音恢复时才后移，保留修正依据与近似标记。这不等于声学VAD；有背景音乐或较高底噪的停顿仍须复核，不能靠RMS确认说了哪一个字。录音文件本身不删停顿。

本地环境准备：

```sh
python3 -m venv PROJECT_DIR/.venv
PROJECT_DIR/.venv/bin/python -m pip install -r SKILL_DIR/scripts/requirements.txt
```

随后Python命令使用这个解释器。本地Whisper模型路径由安装环境查找，不在skill里写死用户名或下载完整大模型作为每次默认操作。转写缺少工具时，可以选择用户已授权的转写器并转换字段；禁止直接均匀分配整稿时间来冒充结果。

关键事件需要更准时，可用支持当前语言的声学强制对齐器，例如WhisperX的已验证本机环境；或者逐段播放和波形检查后人工标记。不要宣称本skill默认已经完成WhisperX强制对齐。人工复核可写`reviewedUnits:{"u2":{"startMs":2100,"endMs":3700,"reason":"依据当前音轨复核该句边界"}}`，保留依据。此方式适合少数疑点，不适合整片没有时间证据的假对齐。更换音轨后删除旧复核时间重新处理。

每个已生成时间线绑定规范音轨SHA256、样本数与采样率。渲染和合音前使用validate_timeline，音轨发生变化即拒绝复用。ASR的出处仍需验证：使用run_asr.py转写并在align时传入`--asr-manifest`，严格核对实际输入和识别输出摘要。没有识别时生成的来源manifest时，重新转写。禁止在导入旧转写时用当前录音临时补写摘要来绕过关联检查。

音频独立合入静音视频。不复制其他工程的2048样本或固定一帧补偿。verify_media解码成片后在多个窗口做相关性测量，报告偏移、相关程度、峰值、完整解码和视频长度。相关性测量只支持音轨复用同步，不能替代字幕内容检查。SFX与BGM若要添加，先做voice-only基准验证；增加混音后复查语音保留与局部峰值，不把强音效窗口用来测语音偏移。

导出SRT：`python3 SKILL_DIR/scripts/export_srt.py --timeline PROJECT_DIR/src/timeline.json --output PROJECT_DIR/out/captions.srt`。
