# 豆包配音与返工

默认：豆包TTS2.0，resourceId `seed-tts-2.0`，美式女声Dacey `en_female_dacey_uranus_bigtts`，24kHz单声道PCM16，封装WAV。系统音色及账户权限以控制台为准。

凭证只从进程环境`DOUBAO_TTS_API_KEY`读取，不自动加载.env。如果用户将Key存入.env，在本机以安全方式导出变量后运行，不打印变量值。请勿提交.env。`audio --dry-run`不访问网络，列出42段示例（24单词+18故事段落）、待合成字符数、已校验缓存命中；字符数不是价格或账单。

可选`--config voice.json`只允许provider、resourceId、speaker、sampleRate、speechRate、timeoutSeconds，字段默认见scripts/audio.py；禁止在配置放凭证。

`audio`逐个请求，完成码20000000后才接纳PCM数据。断流与临时错误最多尝试3次，参数/鉴权/余额等错误立即停止；中断后重跑复用已校验缓存。章节由完整段落连接，cues按采样数计算；不是逐词同步。

缓存位于输出目录的.cache/，以文本+声线配置哈希为键，同时验证完成码、内容摘要、WAV解码和采样率。改一段英语只重做相应段落并重组章节，改全局声线会失效全部缓存。中文或解释更改也使发布清单旧哈希失效，但不改变英语音段缓存。

真实音频完成后逐个核听单词及章节，留意多词性发音（如suspect）、漏读、重复、专名和文本对应。文件可解码与缓存有效不能替代核听。

本次样包按用户指示暂缓真实配音。适配器通过模拟协议与异常测试，未用本账户完成真实API集成；后续首次接入需验证Key、Dacey权限和实际发音，再核听发布。

协议核对入口（2026-10-20）：
- [单向流式HTTP V3接口](https://www.volcengine.com/docs/6561/1598757)
- [官方音色列表](https://docs.volcengine.com/docs/DoubaoVoice/Tonelist-1?lang=zh)

脚本为本项目独立实现，运行时不导入本机视频/自媒体工作流，无第三方SDK依赖。

用户取消章节朗读时用book.chapter_narration=false。此时dry-run仅列单词，generate/inspect/package只处理词级文件；章节朗读已取消，不是配音待做。旧缓存和历史待合成文本不批量删除，当前交付清单不再包含章节合成任务。
