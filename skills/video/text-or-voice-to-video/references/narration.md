# 文字稿与豆包配音

仅提供文字稿时读取此文档；已有录音不需要豆包配置。稿件准备和配音脚本均仅依赖Python标准库，后续音频处理、Whisper与Remotion按主技能准备。

## 账号和本机配置

在[豆包语音控制台](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default)完成账号要求，开通豆包语音合成2.0，创建语音服务API Key并检查试用额度/付费状态。这不是通用方舟聊天模型密钥。参考[官方API说明](https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh)和[API Key说明](https://docs.volcengine.com/docs/DoubaoVoice/APIKeyUsage?lang=zh)。

在运行脚本的本机进程环境中设置`DOUBAO_TTS_API_KEY`，不要把真实密钥贴到聊天、提交进工程，或写进narration.json。shell变量须export才能传给子进程；已在别的终端设置不代表当前Codex进程可见。运行`--dry-run`只输出是否配置，不输出值；也可在设置好环境的终端执行配音命令。

## 新工程

先运行init_project.py，写好UTF-8稿件文件，然后按顺序运行；大写占位符须替换为实际绝对路径：

```sh
python3 SKILL_DIR/scripts/prepare_script.py --input MANUSCRIPT --output-dir PROJECT_DIR --replace-script
python3 SKILL_DIR/scripts/synthesize_narration.py --script PROJECT_DIR/script.json --config PROJECT_DIR/narration.json --output-dir PROJECT_DIR/out/narration --dry-run
python3 SKILL_DIR/scripts/synthesize_narration.py --script PROJECT_DIR/script.json --config PROJECT_DIR/narration.json --output-dir PROJECT_DIR/out/narration
python3 SKILL_DIR/scripts/prepare_audio.py --input PROJECT_DIR/out/narration/voice.wav --output-dir PROJECT_DIR/out/audio
```

粘贴稿件优先通过文件工具保存为TXT，再传`--input`。程序化调用也可用prepare_script.py的`--text`参数，经参数数组传入，禁止把正文拼进shell。`--markdown`用于清理--text里的Markdown；文件按.md/.markdown后缀识别。--title和--fps可覆盖标题与帧率。

保留manuscript.original.txt/md；重新准备时旧原稿归档到manuscript-history。manuscript.txt是格式整理后的朗读稿；script.json是配音与字幕的最终文本来源。Markdown标题、链接标签、强调文本、引用和代码内容会保留，外观符号被清理；复杂表格、公式、专有词应人工检查，不自动改写。script的unit ID基于句子内容，重复句附出现序号；新增paragraphId只用于合成分组，不改变已有时间线契约。

第一次--replace-script替换模板草案；后续该选项会重建句段和草案分镜，不能用它覆盖已经设计的场景而不检查。通常直接修改script.json中需要改的句子即可。

## 配音配置

工程中的narration.json示例：

```json
{
  "provider": "doubao",
  "resourceId": "seed-tts-2.0",
  "speaker": "zh_female_vv_uranus_bigtts",
  "speechRate": 0,
  "sampleRate": 24000,
  "maxChunkChars": 300,
  "timeoutSeconds": 60
}
```

首版仅支持seed-tts-2.0系统音色，speaker必须与资源版本匹配且已获账号权限。语速speechRate范围-50到100，0为原速；sampleRate默认24000。maxChunkChars范围1到300，按自然段组合完整句子，长句超过上限时按字符拆分，正文不截断。旧script没有paragraphId时每个unit单独分组。不要为追求某个秒数先分配虚构的字幕时间。

请求发送到固定官方HTTPS地址，使用X-Api-Key、X-Api-Resource-Id、随机X-Api-Request-Id，禁止重定向转发凭证。输出请求PCM格式，按行处理NDJSON，base64顺序解码；网络chunk不能当作JSON边界。只有业务结束码20000000且存在完整PCM16音频时才成功，EOF不是成功信号。保存为单声道WAV，再由prepare_audio生成48k规范副本。服务端词时间戳不作为首版正式对齐来源。

## 缓存、失败与用量

out/narration/cache按文本、资源版本、音色、语速、采样率缓存WAV及摘要，校验结束码、SHA256和完整PCM后才复用。同一分段复用无需API调用；改一段只重做变化分段，换音色/语速使对应缓存失效。并行运行同一项目不受支持；等前一任务结束再运行。

out/narration/progress.json记录完成分段和状态。临时网络错误、HTTP限流和服务暂时错误最多重试两次，间隔1秒/2秒；认证、额度、参数和音色错误立即停止。错误日志只保留状态码与客户端提示，不输出凭证或服务端原文。流中断的音频丢弃，不缓存为完成结果。再次执行相同命令从已校验分段恢复。

新一轮正式合成会使旧voice.wav和成功manifest失效；失败时不能继续用public/audio中的旧副本渲染新稿。--dry-run不写文件、不调用服务，不会删除旧结果。只验证全部缓存时可不提供密钥；有任何缺失分段都需要密钥。

成功后out/narration/voice.wav是完整AI旁白，narration.manifest.json记录音轨摘要、输入稿件摘要、音色、参数、分段来源和用量。newlyBilledTextWords表示本次成功请求最后返回的usage.text_words之和；缺少usage时usageComplete=false，不能当作免费。缓存分段沿用历史用量，但不计入本轮新调用；重试和失败请求可能也产生费用，failedRequestsMayHaveUsage提示这种不确定性，以控制台结算为准。

## 接回画面与验收

配音成功后继续主技能第6步，真实运行Whisper，核对漏读、重复、数字和专有词，按当前音轨生成timeline。换音轨必须删除旧reviewedUnits并重新复核；原有音轨SHA256、ASR manifest、script摘要检查保持不变。先完成内容分镜与三张静帧检查，再渲染、合音及verify_media，不把模板卡片视为设计定版。

导出SRT，交付MP4、旁白、工程、素材来源、配音manifest与QA；在工程和交付说明明确标注AI合成。编码同步的8ms偏移/5ms漂移检查不能替代内容与字幕复核。缺少真实凭证时只报告本地测试范围，不用测试信号或其他声音冒充豆包样片。
