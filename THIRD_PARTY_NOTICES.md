# 第三方内容与权利说明

本仓库的自定义许可仅覆盖不吃辣的Chris有权授权的内容，不能代替上游许可或为来源不明的素材补授权限。来源目录记录不等于完整的版权证明。未标明许可不等于可以任意使用。

## 内容来源与边界

| 内容 | 已知来源 | 许可处理 |
| --- | --- | --- |
| 分类 Skill 的来源副本 | 根目录 SOURCES.md 与 catalog.json 记录的本机项目；规格书 Skill 来自归档上传包 | 本人有权授权的部分适用 LICENSE；来源记录本身不证明所有文件原创，遇到第三方标记应保留并按其授权处理 |
| 故事词汇工作室 | skills/education/story-vocabulary-studio/；来源见 SOURCES.md 与 catalog.json | 原包未附独立许可，仓库许可仅覆盖本人有权授权的内容；外部词表、考试材料和豆包音频服务规则独立适用，详见包内 THIRD_PARTY_NOTICES.md |
| 项目主线导读 | skills/development/project-flow-guide/；原名 project-xray，来源见 SOURCES.md 与 catalog.json | 原包未附独立许可；保留完整指导与参考文件，仅调整技能名称和调用元数据，仓库许可仅覆盖本人有权授权的内容，详见包内 THIRD_PARTY_NOTICES.md |
| 电商视频爆款拆解 | skills/ecommerce/ecommerce-video-breakdown/；来源见 SOURCES.md 与 catalog.json | 媒体取材模块已在本仓库重新实现；保留来源版本与修改记录，仓库许可仅覆盖本人有权授权的内容，平台协议、视频素材与外部工具依赖按各自权利使用，详见包内 THIRD_PARTY_NOTICES.md |
| 视频链接批量归档 | skills/video/media-urls-batch-archive/；来源为本机已安装 Skill | 保留来源版本的开发与工具依赖说明；仓库许可仅覆盖本人有权授权的流程代码与文档，yt-dlp、FFmpeg、字幕与语音识别工具、模型适用各自许可 |
| 按参考换商品套图 | skills/ecommerce/ecommerce-reference-product-swap/；来源为本机已安装 Skill | 原包未附独立许可文件；本人有权授权的部分适用 LICENSE，宿主生图服务与 Pillow 等工具独立适用各自条款，用户参考、商品、人物与品牌素材不随包授权 |
| 多源故障切换生图 | 用户指定的 failover-imagegen-tool-sanitized.zip；解包至 skills/image/failover-imagegen-tool/ | 10个来源文件原样保留；源包未附独立许可，仓库许可仅覆盖本人有权授权的内容；Python、Tcl/Tk、中转服务、模型与素材适用各自权利说明，详见包内 THIRD_PARTY_NOTICES.md |
| 商品人物自然试穿 | 用户指定的 ecommerce/person-tryon/skills/product-person-tryon；来源见 SOURCES.md 与 catalog.json | 两份指导及元数据源文件原样保留，仓库许可仅覆盖本人有权授权的内容；宿主图像工具及用户人物、商品与场景素材按各自权利使用，不收录真实样图，详见包内 THIRD_PARTY_NOTICES.md |
| B站视频解析工具箱 | 用户提供的 bilibili-toolkit.zip；解包至 skills/video/bilibili-toolkit/ | 六个来源文件原样保留，源包未附独立许可或作者信息；仓库许可仅覆盖本人有权授权的内容。媒体、字幕、模型及平台权利独立适用，详见包内 THIRD_PARTY_NOTICES.md |
| 租赁公司签约前尽调 | 用户指定的 intelligence/rental-company-due-diligence/skills/rental-company-due-diligence；来源见 SOURCES.md 与 catalog.json | 原样保留9个源文件及外部方法来源记录，另补入同项目单元测试；许可仅覆盖本人有权授权的内容，公开来源、工具与用户材料独立适用权利说明，详见包内 THIRD_PARTY_NOTICES.md |
| 人际冲突 Skill 及历史 HTML 案例 | skills/communication/deal-with-jerks/ | 本人有权授权的部分适用 LICENSE；历史案例不作为事实或咨询质量的证明 |
| 模板库电商生图工作流及八张模板参考图 | workflows/ecommerce/ecommerce-template-image-workflow/；来源见 SOURCES.md 与 catalog.json | 源目录未附许可或逐图权利证明；本人有权授权的部分适用 LICENSE，模板参考图使用前需核实授权，详见工程 THIRD_PARTY_NOTICES.md |
| 商品图、模特参考图与生成场景图 | assets/examples/sources.json 所列原始项目和博客资产 | 可能涉及摄影、肖像、商标、商品设计及生成服务条款；不授予独立转载、商业使用或品牌背书权限 |
| 外文服装规格书 PDF、原稿与批注成品 | 用户提供材料及 coding-blog 归档 | 原稿及所含第三方信息的权利仍归相应权利人；上传或展示不等于可转授权 |
| 原录音、口播稿、字幕、视频、表格截图 | assets/examples/sources.json 所列来源 | 本人有权授权的部分受 LICENSE 约束；其他素材及输出仍须核对各自权利 |
| AI 生成的 README 配图 | assets/readme/IMAGE-SOURCE.md 及对应记录 | 按生成服务条款及适用法律处理；不保证全部元素具有可主张的著作权 |
| 历史 README 分类目录 SVG 总览 | assets/readme/toolbox-overview.svg，根据 README 与 catalog.json 编排 | 本仓库制作，仅包含文字与基础图形，使用系统字体回退，不随图分发字体文件 |

## 外部依赖和服务

下列为根据当前清单及使用说明识别的主要外部组件，不是逐项完成的法律审计或完整依赖清单。

- 飞书工作流：openai、adm-zip、zod，以及 TypeScript、tsx、Vitest 和类型包等开发依赖；完整版本和传递依赖见对应 package-lock.json。
- 视频工程：Remotion 及 @remotion/*、React、React DOM、TypeScript 和类型包；完整版本和传递依赖见 starter/package-lock.json。
- Python 与媒体处理：numpy、opencc-python-reimplemented、Pillow（相关渲染脚本使用）、FFmpeg/FFprobe、Whisper CLI 及所使用的识别模型；以实际安装组件为准。
- 模板库电商生图工作流：Pillow、PyYAML、pytest；依赖要求见工程 requirements.txt，各组件适用各自许可。
- 故事词汇工作室：运行脚本仅使用 Python 标准库，阅读器使用原生 HTML/CSS/JavaScript；可选豆包 TTS 的账户、音色权限、计费及音频使用条款独立适用。
- 电商视频爆款拆解：FFmpeg/FFprobe、yt-dlp、static-ffmpeg、可选本地 Whisper/faster-whisper，以及按需使用的 Node/宿主表格工具；不分发已安装依赖、模型、账号资料或原视频，具体依赖见包内 assets/requirements*.txt。
- 视频链接批量归档：Python、yt-dlp、youtube-transcript-api、static-ffmpeg、FFmpeg/FFprobe、faster-whisper、PyAV、CTranslate2 及 Whisper 模型；按目标电脑安装，版本范围见包内 requirements*.txt，不随仓库分发已安装运行时、模型或凭据。
- 按参考换商品套图：独立导出器使用 Python 3.10+ 与 Pillow，实际图像编辑能力由宿主提供；未随包归集参考图、商品实拍、人物或品牌素材，来源声明与导出校验不构成授权证明。
- 多源故障切换生图：核心实现仅用Python标准库，可选GUI使用tkinter/Tcl/Tk；真实中转服务与模型由使用者配置，服务条款、计费和图片素材权利独立适用，不随源码包分发已安装环境、API Key或真实生成产物。
- 商品人物自然试穿：Skill仅包含指导与Agent元数据，默认使用宿主看图及内置图像工具；不分发图像模型、API凭据、人物参考或真实生成结果。人物、摄影、商品与生成服务权利独立适用。
- B站视频解析工具箱：Python 3.12、faster-whisper、PyAV、CTranslate2、rapidocr-onnxruntime、Pillow 及识别模型；列表整理另依赖额外浏览器技能。原包以 Windows 为例，不分发环境、模型、账号、视频或字幕，版本与平台可用性未在本次收录中验证。
- 租赁公司签约前尽调：可选查询规划器仅用Python标准库；实际调查需要宿主联网、网页阅读和浏览器能力，公开登记、司法、投诉等资料适用来源规则。方法参考及取舍见包内references/adaptation-notes.md，不分发第三方Skill、真实合同或调查结果。
- 外部服务：飞书 API、图片生成服务及其他接入服务，其服务条款、费用和数据规则独立适用。

本仓库的 LICENSE 不覆盖上述第三方组件，不撤销其原许可授予的权限，也不免除其署名、分发、源码提供或付费许可等要求。尤其不得因获得本项目商业授权，就推断已获得 Remotion、模型、字体或素材的全部商业权限。

仓库不分发 node_modules 和上述工具的已安装运行时。安装或分发第三方组件时，应查阅具体版本随附的 LICENSE/NOTICE 及官方条款，保留所要求的声明。发现遗漏或权属问题，可通过本仓库 Issues 联系维护者；确认后补充说明或调整相关材料。
